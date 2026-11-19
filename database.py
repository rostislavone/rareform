"""
Работа с базой данных RAREFORM.

SQLite — база данных в одном файле (rareform.db рядом с этим файлом).
Отдельно ставить ничего не нужно: модуль sqlite3 встроен в Python.
"""

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path

# Где лежит база. На сервере можно задать переменной окружения RAREFORM_DB,
# иначе — rareform.db рядом с этим файлом.
# Path(__file__).parent — папка, где лежит этот файл, откуда бы ни запускали сервер
DB_PATH = Path(os.environ.get("RAREFORM_DB", Path(__file__).parent / "rareform.db"))


def connect():
    """Открывает соединение с базой."""
    conn = sqlite3.connect(DB_PATH)
    # Row позволяет обращаться к колонкам по имени: row["brand"], а не row[1]
    conn.row_factory = sqlite3.Row
    # Включаем связи между таблицами: удалили товар — удалятся и его заказы, предложения, сообщения
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ===== Товары, с которых начинается база =====
# Раньше они жили в products.js. Теперь это начальные данные:
# они записываются в базу один раз, когда таблица ещё пустая.
SEED_PRODUCTS = [
    {
        "id": 1, "brand": "Rick Owens", "title": "Кожаная куртка Stooges", "price": 92999,
        "size": "M, L", "emoji": "🧥", "category": "Верхняя одежда", "condition": "Отличное",
        "color": "Чёрный", "city": "Москва", "seller": "archive_dealer", "rating": 4.9, "sales": 128,
        "photos": ["rick-owens-1.webp", "rick-owens-2.webp", "rick-owens-3.webp", "rick-owens-4.webp"],
        "description": "Оригинальная куртка Rick Owens Stooges из мягкой телячьей кожи. Носилась аккуратно, без повреждений. Отправлю СДЭКом по всей России.",
    },
    {
        "id": 2, "brand": "Maison Margiela", "title": "Кеды Replica", "price": 24500,
        "size": "43", "emoji": "👟", "category": "Обувь", "condition": "Хорошее",
        "color": "Белый / серый", "city": "Санкт-Петербург", "seller": "white_label", "rating": 4.7, "sales": 54,
        "photos": ["margiela-1.webp", "margiela-2.webp", "margiela-3.webp"],
        "description": "Классические кеды Replica из гладкой кожи. Подошва с небольшими следами носки, верх в отличном состоянии. Есть коробка и пыльник.",
    },
    {
        "id": 3, "brand": "Raf Simons", "title": "Футболка оверсайз 2002", "price": 31000,
        "size": "L", "emoji": "👕", "category": "Верх", "condition": "Отличное",
        "color": "Тёмно-серый, красный принт", "city": "Москва", "seller": "archive_dealer", "rating": 4.9, "sales": 128,
        "photos": ["raf-simons-1.webp", "raf-simons-2.webp", "raf-simons-3.webp", "raf-simons-4.webp", "raf-simons-5.webp"],
        "description": "Архивная футболка Raf Simons 2002 года свободного кроя. Принт целый, без трещин. Редкая вещь из коллекции начала двухтысячных.",
    },
    {
        "id": 4, "brand": "Gucci", "title": "Джинсы Horsebit SS26", "price": 95000,
        "size": "32", "emoji": "👖", "category": "Низ", "condition": "Новое с бирками",
        "color": "Белый деним", "city": "Москва", "seller": "luxe_corner", "rating": 5.0, "sales": 37,
        "photos": ["gucci-jeans-1.webp", "gucci-jeans-2.webp", "gucci-jeans-3.webp", "gucci-jeans-4.webp", "gucci-jeans-5.webp"],
        "description": "Джинсы Gucci из коллекции весна-лето 2026 с фирменной металлической деталью Horsebit. Новые, с бирками и оригинальным пакетом.",
    },
    {
        "id": 5, "brand": "Supreme", "title": "Кепка New Era Scream Box Logo", "price": 9900,
        "size": "7 3/8", "emoji": "🧢", "category": "Аксессуары", "condition": "Отличное",
        "color": "Лесной камуфляж", "city": "Казань", "seller": "drop_hunter", "rating": 4.6, "sales": 211,
        "photos": ["supreme-1.webp", "supreme-2.webp", "supreme-3.webp"],
        "description": "Кепка Supreme × Scream на базе New Era 59FIFTY в лесном камуфляже. Спереди вышитый Box Logo, сзади маска из «Крика» и надпись World Famous. Закрытая спинка, размер 7 3/8 (58,7 см). Почти не носилась.",
    },
    {
        "id": 6, "brand": "Guidi", "title": "Ботинки 788Z", "price": 72000,
        "size": "42", "emoji": "🥾", "category": "Обувь", "condition": "Хорошее",
        "color": "Чёрный", "city": "Москва", "seller": "white_label", "rating": 4.7, "sales": 54,
        "photos": ["guidi-1.webp", "guidi-2.webp"],
        "description": "Ботинки Guidi 788Z из лошадиной кожи ручной работы. Кожа красиво разносилась, подошва в хорошем состоянии.",
    },
    {
        "id": 7, "brand": "Comme des Garçons", "title": "Свитер Homme Plus", "price": 27000,
        "size": "M", "emoji": "🧶", "category": "Верх", "condition": "Отличное",
        "color": "Коричневый, узор пейсли", "city": "Екатеринбург", "seller": "tokyo_archive", "rating": 4.8, "sales": 89,
        "photos": ["cdg-1.webp", "cdg-2.webp", "cdg-3.webp", "cdg-4.webp"],
        "description": "Шерстяной свитер Comme des Garçons Homme Plus с асимметричным кроем. Без катышков и затяжек.",
    },
    {
        "id": 8, "brand": "Gucci", "title": "Оправа GG1085O 001", "price": 32000,
        "size": "OS", "emoji": "👓", "category": "Аксессуары", "condition": "Новое",
        "color": "Чёрный", "city": "Москва", "seller": "luxe_corner", "rating": 5.0, "sales": 37,
        "photos": ["gucci-glasses-1.webp", "gucci-glasses-2.webp"],
        "description": "Оптическая оправа Gucci GG1085O, цвет 001 (чёрный). Можно вставить линзы под своё зрение. Новая, в фирменном футляре.",
    },
]

# Порядок колонок — используем и при создании таблицы, и при вставке
COLUMNS = ["id", "brand", "title", "price", "size", "emoji", "category", "condition",
           "color", "city", "seller", "rating", "sales", "photos", "description"]


def init_db():
    """Создаёт таблицы, обновляет старую базу и заполняет её начальными товарами."""
    # closing(...) закроет соединение в конце, а второй with conn — сохранит изменения (commit)
    with closing(connect()) as conn, conn:
        # executescript выполняет сразу несколько команд SQL, разделённых точкой с запятой
        conn.executescript("""
            -- ===== Пользователи =====
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,  -- UNIQUE: два аккаунта на одну почту база не пустит
                password_hash TEXT NOT NULL,         -- не сам пароль, а его «отпечаток»
                is_admin      INTEGER DEFAULT 0,     -- 1 — администратор сайта
                is_blocked    INTEGER DEFAULT 0,     -- 1 — заблокирован администратором
                created_at    TEXT DEFAULT (datetime('now'))
            );

            -- ===== Сессии: кто сейчас вошёл =====
            -- После входа браузер получает случайный токен в cookie. В базе храним
            -- не сам токен, а его хеш: даже утёкшая база не даст войти в чужой аккаунт.
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );

            -- ===== Товары =====
            CREATE TABLE IF NOT EXISTS products (
                -- AUTOINCREMENT: номер удалённого товара никогда не достанется новому,
                -- иначе в чужом избранном вместо удалённой вещи появилась бы другая
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                brand       TEXT NOT NULL,
                title       TEXT NOT NULL,
                price       INTEGER NOT NULL,      -- цена в рублях
                size        TEXT,
                emoji       TEXT,
                category    TEXT,
                condition   TEXT,
                color       TEXT,
                city        TEXT,
                seller      TEXT,
                rating      REAL,
                sales       INTEGER DEFAULT 0,
                photos      TEXT DEFAULT '[]',     -- список имён файлов, записанный как JSON-строка
                description TEXT,
                -- Кто выставил. У стартовых товаров пусто (NULL).
                -- ON DELETE SET NULL: удалили аккаунт — товар остаётся, но без владельца
                user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL
            );

            -- ===== Заказы, предложения цены и сообщения продавцу =====
            -- product_id REFERENCES products(id) — связь с товаром.
            -- ON DELETE CASCADE — когда товар удаляют, его записи удаляются вместе с ним.
            -- buyer_id — кто отправил. created_at заполняется текущим временем (UTC)
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                buyer_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
                name       TEXT NOT NULL,
                phone      TEXT NOT NULL,
                delivery   TEXT NOT NULL,
                total      INTEGER NOT NULL,           -- итог считает сервер, а не браузер
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS offers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                buyer_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
                amount     INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                buyer_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
                text       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # ===== Избранное =====
        # Пара (пользователь, товар) — PRIMARY KEY из двух колонок:
        # один товар нельзя добавить в избранное одному человеку дважды
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, product_id)
            )
        """)

        # ===== Миграция: обновляем базу, созданную прошлой версией кода =====
        # CREATE TABLE IF NOT EXISTS не трогает уже существующие таблицы,
        # поэтому недостающие колонки добавляем, а ненужные убираем сами.
        product_columns = column_names(conn, "products")
        if "owner_token" in product_columns:
            # Секретные ключи объявлений больше не нужны — теперь владелец это аккаунт
            conn.execute("ALTER TABLE products DROP COLUMN owner_token")
        if "user_id" not in product_columns:
            conn.execute("ALTER TABLE products ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        if "is_blocked" not in column_names(conn, "users"):
            conn.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")
        for table in ("orders", "offers", "messages"):
            if "buyer_id" not in column_names(conn, table):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN buyer_id INTEGER REFERENCES users(id) ON DELETE SET NULL")

        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            # Знаки ? — места для значений. Подставлять значения через ?, а не склеивать
            # строку вручную, — защита от SQL-инъекций (когда в данных спрятана команда для базы)
            placeholders = ", ".join("?" for _ in COLUMNS)
            conn.executemany(
                f"INSERT INTO products ({', '.join(COLUMNS)}) VALUES ({placeholders})",
                [[json.dumps(p[c], ensure_ascii=False) if c == "photos" else p[c] for c in COLUMNS]
                 for p in SEED_PRODUCTS],
            )


def column_names(conn, table):
    """Названия колонок таблицы. PRAGMA table_info возвращает по строке на колонку."""
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


# ===== Пароли =====
# Пароль никогда не хранится как есть. scrypt превращает его в «отпечаток» (хеш):
# из отпечатка пароль не восстановить, а проверить — можно, посчитав отпечаток заново.
# Соль — случайные байты, свои у каждого пользователя: одинаковые пароли дают разные отпечатки.
# scrypt специально медленный и требует много памяти — так перебор паролей очень дорог.

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password, stored):
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    # compare_digest сравнивает за одинаковое время — по скорости ответа ничего не угадать
    return secrets.compare_digest(digest.hex(), digest_hex)


# ===== Пользователи =====

def public_user(row):
    """Только то, что можно показать в браузере. Хеш пароля наружу не отдаём никогда."""
    return {"id": row["id"], "name": row["name"], "email": row["email"],
            "is_admin": bool(row["is_admin"]), "is_blocked": bool(row["is_blocked"])}


def create_user(name, email, password, is_admin=False):
    """Новый пользователь. None, если почта уже занята."""
    try:
        with closing(connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                (name, email, hash_password(password), int(is_admin)),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return public_user(row)
    except sqlite3.IntegrityError:  # сработал UNIQUE на почте
        return None


def check_login(email, password):
    """Пользователь, если почта и пароль верные, иначе None."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        # Всё равно считаем хеш: иначе по скорости ответа можно узнать, есть ли такая почта
        check_password(password, DUMMY_HASH)
        return None
    return public_user(row) if check_password(password, row["password_hash"]) else None


DUMMY_HASH = hash_password("nobody-has-this-password")


# ===== Сессии =====

SESSION_DAYS = 30


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id):
    """Новая сессия. Возвращает токен для cookie — в базе только его хеш."""
    token = secrets.token_urlsafe(32)
    with closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
            (token_hash(token), user_id, f"+{SESSION_DAYS} days"),
        )
    return token


def get_session_user(token):
    """Пользователь по токену из cookie или None, если сессии нет или она истекла."""
    if not token:
        return None
    with closing(connect()) as conn:
        row = conn.execute(
            """SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ? AND sessions.expires_at > datetime('now')
                 AND users.is_blocked = 0  -- заблокированный сразу перестаёт быть «вошедшим»
            """,
            (token_hash(token),),
        ).fetchone()
    return public_user(row) if row else None


def delete_session(token):
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token or ""),))


# ===== Товары =====

def row_to_product(row):
    """Строка из базы → обычный словарь. Фото из JSON-строки снова становятся списком."""
    product = dict(row)
    product["photos"] = json.loads(product["photos"] or "[]")
    return product


def get_products():
    """Все товары, новые первыми."""
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return [row_to_product(r) for r in rows]


def get_product(product_id):
    """Один товар по номеру или None, если такого нет."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return row_to_product(row) if row else None


def get_user_products(user_id):
    """Объявления одного пользователя."""
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM products WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    return [row_to_product(r) for r in rows]


def create_product(data, user_id):
    """Добавляет товар от имени пользователя. data — поля товара без id."""
    values = {**data, "photos": json.dumps(data["photos"], ensure_ascii=False), "user_id": user_id}
    names = list(values)
    with closing(connect()) as conn, conn:
        cursor = conn.execute(
            f"INSERT INTO products ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})",
            [values[n] for n in names],
        )
        new_id = cursor.lastrowid  # id, который база выдала новой строке
    return get_product(new_id)


def can_manage(product, user):
    """Управлять товаром может его владелец или администратор."""
    return bool(user) and (user["is_admin"] or product["user_id"] == user["id"])


def delete_product(product_id):
    """Удаляет товар. Возвращает список его фото, чтобы сервер стёр файлы."""
    product = get_product(product_id)
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    return product["photos"] if product else []


# ===== Для администратора =====

def get_stats():
    """Сводка по сайту: сколько чего. COALESCE(x, 0) — если заказов нет, сумма будет 0, а не пусто."""
    with closing(connect()) as conn:
        def count(sql):
            return conn.execute(sql).fetchone()[0]
        return {
            "users": count("SELECT COUNT(*) FROM users"),
            "products": count("SELECT COUNT(*) FROM products"),
            "orders": count("SELECT COUNT(*) FROM orders"),
            "revenue": count("SELECT COALESCE(SUM(total), 0) FROM orders"),
            "offers": count("SELECT COUNT(*) FROM offers"),
            "messages": count("SELECT COUNT(*) FROM messages"),
        }


def list_users():
    """Все пользователи с числом объявлений и покупок. Хеши паролей сюда не попадают."""
    with closing(connect()) as conn:
        # Подзапрос в скобках считает объявления и покупки для каждой строки users
        rows = conn.execute("""
            SELECT id, name, email, is_admin, is_blocked, created_at,
                   (SELECT COUNT(*) FROM products WHERE products.user_id = users.id) AS listings,
                   (SELECT COUNT(*) FROM orders WHERE orders.buyer_id = users.id) AS purchases
            FROM users ORDER BY id DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_user(user_id):
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row) if row else None


def set_blocked(user_id, blocked):
    """Блокирует или разблокирует. При блокировке удаляем все сессии — человека сразу выкидывает."""
    with closing(connect()) as conn, conn:
        conn.execute("UPDATE users SET is_blocked = ? WHERE id = ?", (int(blocked), user_id))
        if blocked:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def list_all_orders():
    """Все заказы сайта: товар, продавец, покупатель."""
    with closing(connect()) as conn:
        rows = conn.execute("""
            SELECT orders.id, orders.total, orders.delivery, orders.name, orders.phone, orders.created_at,
                   products.id AS product_id, products.brand, products.title, products.seller,
                   users.name AS buyer_name, users.email AS buyer_email
            FROM orders
            JOIN products ON products.id = orders.product_id
            LEFT JOIN users ON users.id = orders.buyer_id
            ORDER BY orders.id DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ===== Избранное =====

def get_favorite_ids(user_id):
    """Номера товаров в избранном, последние добавленные первыми."""
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT product_id FROM favorites WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
    return [r["product_id"] for r in rows]


def add_favorite(user_id, product_id):
    # INSERT OR IGNORE — если такая пара уже есть, просто ничего не делаем, без ошибки
    with closing(connect()) as conn, conn:
        conn.execute("INSERT OR IGNORE INTO favorites (user_id, product_id) VALUES (?, ?)", (user_id, product_id))


def remove_favorite(user_id, product_id):
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND product_id = ?", (user_id, product_id))


# ===== Заказы, предложения, сообщения =====

def add_order(product_id, buyer_id, name, phone, delivery, total):
    with closing(connect()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO orders (product_id, buyer_id, name, phone, delivery, total) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, buyer_id, name, phone, delivery, total),
        )
        return cursor.lastrowid


def add_offer(product_id, buyer_id, amount):
    with closing(connect()) as conn, conn:
        return conn.execute(
            "INSERT INTO offers (product_id, buyer_id, amount) VALUES (?, ?, ?)", (product_id, buyer_id, amount)
        ).lastrowid


def add_message(product_id, buyer_id, text):
    with closing(connect()) as conn, conn:
        return conn.execute(
            "INSERT INTO messages (product_id, buyer_id, text) VALUES (?, ?, ?)", (product_id, buyer_id, text)
        ).lastrowid


def get_inbox(product_id):
    """Всё, что пришло по товару: заказы, предложения и сообщения, новые первыми, с именем отправителя."""
    with closing(connect()) as conn:
        inbox = {}
        for table in ("orders", "offers", "messages"):
            # Имя таблицы берём только из нашего списка выше, поэтому его можно вставить в строку.
            # Значения от пользователя — только через ?
            # LEFT JOIN — подтягиваем имя покупателя из users, даже если аккаунт уже удалён
            rows = conn.execute(
                f"""SELECT {table}.*, users.name AS buyer_name FROM {table}
                    LEFT JOIN users ON users.id = {table}.buyer_id
                    WHERE {table}.product_id = ? ORDER BY {table}.id DESC""",
                (product_id,),
            )
            inbox[table] = [dict(r) for r in rows]
        return inbox


def get_user_orders(user_id):
    """Покупки пользователя вместе с данными товара."""
    with closing(connect()) as conn:
        rows = conn.execute(
            """SELECT orders.id, orders.total, orders.delivery, orders.created_at,
                      products.id AS product_id, products.brand, products.title, products.photos
               FROM orders JOIN products ON products.id = orders.product_id
               WHERE orders.buyer_id = ? ORDER BY orders.id DESC""",
            (user_id,),
        ).fetchall()
    return [row_to_product(r) for r in rows]  # row_to_product заодно разберёт photos