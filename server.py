"""
Сервер RAREFORM на FastAPI.

Делает две вещи:
1. Отдаёт страницы сайта: index.html, style.css, картинки и так далее.
2. Отвечает на запросы к данным по адресам /api/...

Запуск (из папки сайта, после активации окружения .venv):
    python -m uvicorn server:app --reload --port 5500
--reload перезапускает сервер сам, когда меняешь .py-файлы.
"""

import base64
import binascii
import os
import time
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

import database

ROOT = Path(__file__).parent

# Сюда сохраняются фото из формы «Продать»
UPLOADS = ROOT / "images" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

# ===== Настройки =====
# Берутся из переменных окружения — так один и тот же код работает и дома, и на сервере.
# os.environ.get("ИМЯ", "значение по умолчанию"): если переменной нет, берётся значение по умолчанию.
# На сервере переменные задаются в файле /etc/rareform.env (см. папку deploy).

# production — сайт работает в интернете; иначе — домашний режим разработки
PRODUCTION = os.environ.get("RAREFORM_ENV") == "production"

# Аккаунты с этими почтами при регистрации становятся администраторами:
# могут удалить любое объявление и читать входящие по любому товару.
# Несколько почт — через запятую
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.environ.get("RAREFORM_ADMIN_EMAILS", "fckingblazer@gmail.com").split(",")
    if email.strip()
}

# В интернете автоматическую документацию API (/docs) выключаем: незачем показывать всем устройство сервера
app = FastAPI(
    title="RAREFORM",
    docs_url=None if PRODUCTION else "/docs",
    redoc_url=None if PRODUCTION else "/redoc",
    openapi_url=None if PRODUCTION else "/openapi.json",
)

# Перед стартом создаём базу, обновляем её и заполняем, если она пустая
database.init_db()


# ===== Защита для работы в интернете =====

# Middleware — код, который выполняется для КАЖДОГО запроса до и после обработчика
MAX_BODY_BYTES = 20 * 1024 * 1024  # 20 МБ: 5 фото по 3 МБ плюс запас


@app.middleware("http")
async def protect(request: Request, call_next):
    # 1. Слишком большой запрос отклоняем сразу, не читая его: так сервер не завалить гигантским файлом
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "Слишком большой запрос"}, status_code=413)

    response = await call_next(request)

    # 2. Защитные заголовки ответа:
    # nosniff — браузер не будет «угадывать» тип файла (картинку не выполнит как скрипт)
    # DENY — наш сайт нельзя встроить в чужую страницу и подсунуть под невидимые кнопки
    # Referrer-Policy — при переходе на чужой сайт не передаём ему полный адрес нашей страницы
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Ограничение частоты: не больше limit действий за seconds секунд с одного «ключа»
# (адреса или аккаунта). Храним в памяти: {ключ: [время, время, ...]}
RECENT_ACTIONS = {}


def rate_limit(key, limit, seconds):
    now = time.monotonic()
    # оставляем только действия за последние seconds секунд
    recent = [t for t in RECENT_ACTIONS.get(key, []) if now - t < seconds]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="Слишком часто. Подожди немного и попробуй снова.")
    recent.append(now)
    RECENT_ACTIONS[key] = recent


def client_ip(request):
    # Через туннель настоящий адрес посетителя приходит в заголовке, uvicorn сам его подставляет
    return request.client.host if request.client else "unknown"


# ===== Кто сейчас вошёл =====
# После входа браузер хранит cookie "session" и сам присылает её с каждым запросом.
# Depends — «зависимость»: FastAPI сам вызовет функцию и передаст результат в обработчик.

SESSION_COOKIE = "session"


def current_user(session: Annotated[str | None, Cookie()] = None):
    """Пользователь по cookie или None, если не вошёл."""
    return database.get_session_user(session)


def require_user(user: Annotated[dict | None, Depends(current_user)]):
    """То же, но без входа — ошибка 401 «нужно войти»."""
    if user is None:
        raise HTTPException(status_code=401, detail="Нужно войти в аккаунт")
    return user


def require_admin(user: Annotated[dict, Depends(require_user)]):
    """Только администратор, остальным — 403 «нет доступа»."""
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Только для администратора")
    return user


# Короткие имена для подсказок типов в обработчиках ниже
User = Annotated[dict, Depends(require_user)]
MaybeUser = Annotated[dict | None, Depends(current_user)]
Admin = Annotated[dict, Depends(require_admin)]


# ===== Аккаунты =====

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"  # что-то@что-то.что-то


class RegisterIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=40)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


def start_session(request, response, user):
    """Создаёт сессию и кладёт её токен в cookie."""
    token = database.create_session(user["id"])
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=database.SESSION_DAYS * 24 * 3600,
        httponly=True,   # JavaScript на странице не может прочитать cookie — её не украсть скриптом
        samesite="lax",  # чужой сайт не сможет отправить запрос от твоего имени
        # secure — cookie только по HTTPS. Дома сайт открыт по http, поэтому включаем,
        # только когда сам запрос пришёл по https (через туннель или на настоящем сервере)
        secure=request.url.scheme == "https",
    )


@app.post("/api/register", status_code=201)
def register(data: RegisterIn, request: Request, response: Response):
    rate_limit(("register", client_ip(request)), limit=5, seconds=3600)  # 5 аккаунтов в час с адреса
    email = data.email.lower()  # почту храним маленькими буквами: Ivan@Mail.ru = ivan@mail.ru
    user = database.create_user(data.name, email, data.password, is_admin=email in ADMIN_EMAILS)
    if user is None:
        raise HTTPException(status_code=409, detail="Эта почта уже зарегистрирована")
    start_session(request, response, user)
    return user


# Защита от подбора пароля: после 5 ошибок подряд вход с этой почты закрыт на 5 минут.
# Храним в памяти сервера: {почта: [число ошибок, время первой ошибки]}
FAILED_LOGINS = {}
MAX_FAILS = 5
LOCK_SECONDS = 5 * 60


@app.post("/api/login")
def login(data: LoginIn, request: Request, response: Response):
    # Кроме лимита на одну почту — общий лимит с одного адреса, чтобы не перебирали разные почты
    rate_limit(("login", client_ip(request)), limit=30, seconds=300)
    email = data.email.lower()
    fails, since = FAILED_LOGINS.get(email, (0, 0))
    if fails >= MAX_FAILS and time.monotonic() - since < LOCK_SECONDS:
        raise HTTPException(status_code=429, detail="Слишком много попыток. Подожди 5 минут.")

    user = database.check_login(email, data.password)
    if user is None:
        # Окно 5 минут прошло — начинаем счёт заново
        if time.monotonic() - since >= LOCK_SECONDS:
            fails, since = 0, time.monotonic()
        FAILED_LOGINS[email] = (fails + 1, since)
        # Не говорим, что именно неверно: так нельзя узнать, есть ли такая почта на сайте
        raise HTTPException(status_code=401, detail="Неверная почта или пароль")

    FAILED_LOGINS.pop(email, None)
    # Говорим о блокировке только после верного пароля — иначе по этой ошибке
    # можно было бы узнавать, какие почты зарегистрированы
    if user["is_blocked"]:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован. Напиши нам, если это ошибка.")
    start_session(request, response, user)
    return user


@app.post("/api/logout")
def logout(response: Response, session: Annotated[str | None, Cookie()] = None):
    database.delete_session(session)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(user: MaybeUser):
    """Кто вошёл. {"user": null}, если никто — это не ошибка."""
    return {"user": user}


@app.get("/api/me/products")
def my_products(user: User):
    return database.get_user_products(user["id"])


@app.get("/api/me/orders")
def my_orders(user: User):
    return database.get_user_orders(user["id"])


# ===== Избранное =====
# PUT — «положи», DELETE — «убери». Оба можно повторять: второй PUT ничего не сломает.

@app.get("/api/me/favorites")
def my_favorites(user: User):
    """Номера товаров в избранном."""
    return database.get_favorite_ids(user["id"])


@app.put("/api/me/favorites/{product_id}")
def add_favorite(product_id: int, user: User):
    product_or_404(product_id)  # product_or_404 объявлена ниже — Python найдёт её при вызове
    database.add_favorite(user["id"], product_id)
    return {"ok": True}


@app.delete("/api/me/favorites/{product_id}")
def remove_favorite(product_id: int, user: User):
    database.remove_favorite(user["id"], product_id)
    return {"ok": True}


# ===== Товары =====
# FastAPI сам превращает список словарей в JSON

def product_or_404(product_id):
    product = database.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


def manageable_product(product_id, user):
    """Товар, которым этот пользователь может управлять (свой или он админ), иначе ошибка."""
    product = product_or_404(product_id)
    if not database.can_manage(product, user):
        raise HTTPException(status_code=403, detail="Это не твоё объявление")
    return product


@app.get("/api/products")
def list_products():
    """Все товары."""
    return database.get_products()


@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    """Один товар. product_id: int — FastAPI сам проверит, что в адресе число."""
    return product_or_404(product_id)


# ===== Новое объявление =====

# Pydantic-модель описывает, какие данные мы ждём от формы.
# FastAPI сам проверит каждое поле и вернёт ошибку 422, если что-то не так:
# пустой бренд, цена текстом, неизвестная категория, больше 5 фото...
class ListingIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # убираем пробелы по краям строк

    brand: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=120)
    price: int = Field(gt=0, le=10_000_000)
    size: str = Field(min_length=1, max_length=30)
    # Literal — значение должно быть ровно одним из перечисленных
    category: Literal["Верх", "Низ", "Верхняя одежда", "Обувь", "Аксессуары"]
    condition: Literal["Новое с бирками", "Новое", "Отличное", "Хорошее", "Удовлетворительное"]
    color: str = Field(default="", max_length=60)
    city: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=2000)
    # Фото приходят строками вида "data:image/jpeg;base64,...." — так их готовит форма
    photos: list[str] = Field(default_factory=list, max_length=5)


CATEGORY_EMOJI = {"Верх": "👕", "Низ": "👖", "Верхняя одежда": "🧥", "Обувь": "👟", "Аксессуары": "👜"}

# Какие картинки принимаем: начало data-строки → расширение файла и «подпись» в первых байтах.
# Подпись проверяем, чтобы под видом картинки не прислали другой файл.
IMAGE_TYPES = {
    "data:image/jpeg;base64,": (".jpg", b"\xff\xd8\xff"),
    "data:image/png;base64,": (".png", b"\x89PNG"),
    "data:image/webp;base64,": (".webp", b"RIFF"),
}
MAX_PHOTO_BYTES = 3 * 1024 * 1024  # 3 МБ на одно фото


def save_photo(data_url):
    """Превращает data-строку в файл в images/uploads. Возвращает путь для поля photos."""
    for prefix, (extension, signature) in IMAGE_TYPES.items():
        if data_url.startswith(prefix):
            break
    else:  # for … else: сработает, если цикл не нашёл подходящий тип
        raise HTTPException(status_code=422, detail="Фото должно быть в формате JPEG, PNG или WebP")

    try:
        content = base64.b64decode(data_url[len(prefix):], validate=True)
    except binascii.Error:
        raise HTTPException(status_code=422, detail="Фото повреждено")
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=422, detail="Фото больше 3 МБ")
    if not content.startswith(signature):
        raise HTTPException(status_code=422, detail="Файл не похож на картинку")

    # uuid4 — случайное уникальное имя: файлы разных продавцов не перезапишут друг друга
    name = f"{uuid.uuid4().hex}{extension}"
    (UPLOADS / name).write_bytes(content)
    return f"uploads/{name}"  # путь относительно папки images — как у остальных фото


@app.post("/api/products", status_code=201)
def create_product(listing: ListingIn, user: User):
    """Публикует объявление от имени вошедшего пользователя."""
    rate_limit(("listing", user["id"]), limit=10, seconds=3600)  # 10 объявлений в час — защита от спама
    photos = [save_photo(p) for p in listing.photos]
    data = listing.model_dump()
    data.update(
        photos=photos,
        emoji=CATEGORY_EMOJI[listing.category],
        color=listing.color or "—",
        seller=user["name"],  # продавец — это аккаунт, подделать имя нельзя
        rating=None,          # у нового продавца ещё нет оценок
        sales=0,
    )
    return database.create_product(data, user["id"])


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, user: User):
    """Снимает объявление с продажи. Может владелец или администратор."""
    manageable_product(product_id, user)
    photos = database.delete_product(product_id)
    # Стираем загруженные фото этого товара (стартовые фото из images/ не трогаем)
    for photo in photos:
        if photo.startswith("uploads/"):
            (ROOT / "images" / photo).unlink(missing_ok=True)
    return {"deleted": product_id}


# ===== Заказы, предложения цены, сообщения =====

# Стоимость доставки знает только сервер. Браузер присылает лишь способ доставки:
# если бы он присылал сумму, её легко подменить и «купить» вещь за 1 рубль.
DELIVERY = {
    "cdek": ("СДЭК до пункта выдачи", 500),
    "courier": ("Курьер до двери", 900),
    "pickup": ("Самовывоз", 0),
}


def product_for_buyer(product_id, user):
    """Товар, который этот пользователь может купить: существует и не его собственный."""
    # Заказы, предложения и сообщения вместе — не больше 30 в час с одного аккаунта
    rate_limit(("contact", user["id"]), limit=30, seconds=3600)
    product = product_or_404(product_id)
    if product["user_id"] == user["id"]:
        raise HTTPException(status_code=422, detail="Это твоё объявление")
    return product


class OrderIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=60)
    # pattern — то же правило, что в форме: цифры, пробелы, +, скобки и дефис, 10–20 символов
    phone: str = Field(pattern=r"^[0-9 +()\-]{10,20}$")
    delivery: Literal["cdek", "courier", "pickup"]


@app.post("/api/products/{product_id}/orders", status_code=201)
def create_order(product_id: int, order: OrderIn, user: User):
    product = product_for_buyer(product_id, user)
    delivery_name, delivery_price = DELIVERY[order.delivery]
    total = product["price"] + delivery_price  # цену берём из базы, а не из запроса
    order_id = database.add_order(product_id, user["id"], order.name, order.phone, delivery_name, total)
    return {"id": order_id, "total": total}


class OfferIn(BaseModel):
    amount: int = Field(gt=0)


@app.post("/api/products/{product_id}/offers", status_code=201)
def create_offer(product_id: int, offer: OfferIn, user: User):
    product = product_for_buyer(product_id, user)
    if offer.amount >= product["price"]:
        raise HTTPException(status_code=422, detail="Предложение должно быть меньше цены продавца")
    return {"id": database.add_offer(product_id, user["id"], offer.amount)}


class MessageIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=1000)


@app.post("/api/products/{product_id}/messages", status_code=201)
def create_message(product_id: int, message: MessageIn, user: User):
    product_for_buyer(product_id, user)
    return {"id": database.add_message(product_id, user["id"], message.text)}


@app.get("/api/products/{product_id}/inbox")
def get_inbox(product_id: int, user: User):
    """Входящие по товару. Только владельцу или админу: в заказах имена и телефоны покупателей."""
    manageable_product(product_id, user)
    return database.get_inbox(product_id)


# ===== Панель администратора =====
# Admin в параметрах — FastAPI сначала проверит вход и права, и только потом выполнит функцию

@app.get("/api/admin/stats")
def admin_stats(admin: Admin):
    return database.get_stats()


@app.get("/api/admin/users")
def admin_users(admin: Admin):
    return database.list_users()


@app.get("/api/admin/orders")
def admin_orders(admin: Admin):
    return database.list_all_orders()


class BlockIn(BaseModel):
    blocked: bool


@app.put("/api/admin/users/{user_id}/blocked")
def admin_block_user(user_id: int, data: BlockIn, admin: Admin):
    """Заблокировать ({"blocked": true}) или разблокировать ({"blocked": false})."""
    target = database.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target["is_admin"]:
        raise HTTPException(status_code=422, detail="Администратора заблокировать нельзя")
    database.set_blocked(user_id, data.blocked)
    return {"id": user_id, "blocked": data.blocked}


# ===== Страницы сайта =====
# Картинки — вся папка images
app.mount("/images", StaticFiles(directory=ROOT / "images"), name="images")

# Из корня отдаём только файлы сайта. Так никто не скачает через браузер
# server.py, database.py или саму базу rareform.db.
PUBLIC_TYPES = {".html", ".css", ".js"}

# no-cache — «перед использованием спроси сервер, не изменился ли файл».
# Без этого браузер может долго показывать старую версию style.css или products.js.
# Если файл не менялся, сервер ответит коротким «304 Not Modified», и ничего не скачается заново.
NO_CACHE = {"Cache-Control": "no-cache"}


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html", headers=NO_CACHE)


@app.get("/{filename}")
def site_file(filename: str):
    file = ROOT / filename
    if file.suffix not in PUBLIC_TYPES or not file.is_file():
        raise HTTPException(status_code=404, detail="Страница не найдена")
    return FileResponse(file, headers=NO_CACHE)
