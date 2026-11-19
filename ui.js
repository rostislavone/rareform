// ===== Общие части страниц =====
// products.js хранит данные, а этот файл — то, что нужно сразу нескольким страницам:
// карточка товара и избранное. Подключать ПОСЛЕ products.js.

// ===== Избранное =====
// Вошёл в аккаунт — избранное хранится на сервере и одинаковое на телефоне и компьютере.
// Не вошёл — в localStorage этого браузера, как раньше.
// В обоих случаях номера товаров лежат в favoriteIds — Set, набор без повторов.
// Страница работает с ним сразу, не дожидаясь сервера, а сервер обновляется в фоне.

const FAVORITES_KEY = "rareform-favorites";

function loadLocalFavorites() {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY)) || [];
  } catch {
    return []; // хранилище недоступно или данные испорчены
  }
}

function saveLocalFavorites() {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify([...favoriteIds]));
  } catch {
    // хранилище недоступно — сердечко просто не запомнится
  }
}

let favoriteIds = new Set(loadLocalFavorites());

function isFavorite(id) {
  return favoriteIds.has(id);
}

// Добавляет товар в избранное, а если он там уже есть — убирает.
// Возвращает true, если товар теперь в избранном.
function toggleFavorite(id) {
  const liked = !favoriteIds.has(id);
  if (liked) favoriteIds.add(id);
  else favoriteIds.delete(id);

  if (currentUser) {
    // PUT — добавить, DELETE — убрать. Сердечко уже переключилось, не ждём ответа.
    // Если сервер не принял — возвращаем как было
    fetch(`/api/me/favorites/${id}`, { method: liked ? "PUT" : "DELETE" })
      .then(response => { if (!response.ok) throw new Error(); })
      .catch(() => {
        if (liked) favoriteIds.delete(id);
        else favoriteIds.add(id);
        refreshFavorites();
      });
  } else {
    saveLocalFavorites();
  }
  updateFavoritesCount();
  return liked;
}

// Товары из избранного. Если товар удалили (сняли с продажи), он просто не найдётся.
function getFavoriteProducts() {
  return products.filter(p => favoriteIds.has(p.id));
}

// Обновляет всё на странице, что зависит от избранного: сердечки на карточках и число в шапке.
// Плюс событие "favorites-changed" — страница может подписаться и обновить что-то своё
function refreshFavorites() {
  for (const button of document.querySelectorAll(".like[data-id]")) {
    const liked = favoriteIds.has(Number(button.dataset.id));
    button.classList.toggle("liked", liked);
    button.textContent = liked ? "♥" : "♡";
  }
  updateFavoritesCount();
  document.dispatchEvent(new Event("favorites-changed"));
}

// Число рядом с ♡ в шапке. Пустое, если в избранном ничего нет.
function updateFavoritesCount() {
  const count = getFavoriteProducts().length;
  for (const el of document.querySelectorAll(".fav-count")) {
    el.textContent = count > 0 ? count : "";
  }
}

// ===== Защита от чужого HTML =====
// Тексты объявлений пишут посетители. Если вставить их в страницу через innerHTML как есть,
// название вида <img src=x onerror="..."> выполнится как код у всех, кто откроет каталог.
// escapeHtml заменяет опасные символы кодами — браузер покажет их как обычный текст.
// Правило: всё, что пришло от пользователя и идёт в innerHTML, пропускаем через escapeHtml.
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// «1 вещь», «2 вещи», «5 вещей» — в русском окончание зависит от числа
function itemsWord(n) {
  const last = n % 10, lastTwo = n % 100;
  if (last === 1 && lastTwo !== 11) return `${n} вещь`;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return `${n} вещи`;
  return `${n} вещей`;
}

// ===== Карточка товара =====
// Собирает HTML одной карточки.
// В ссылке передаём id товара: product.html?id=4
// index — номер карточки в сетке: по нему карточки в ряду появляются с небольшой задержкой друг за другом.
// (map сам передаёт номер вторым аргументом: products.map(cardHtml))
function cardHtml(product, index = 0) {
  const photos = getPhotos(product);

  // Фото лежат поверх эмодзи. Если фото нет, видно эмодзи.
  // onerror="this.remove()" — если файл не нашёлся, картинка удаляется.
  // Второе фото появляется при наведении мышки.
  let photosHtml = "";
  if (photos[0]) {
    photosHtml += `<img src="${escapeHtml(photos[0])}" alt="${escapeHtml(product.brand + " " + product.title)}" onerror="this.remove()">`;
  }
  if (photos[1]) {
    photosHtml += `<img src="${escapeHtml(photos[1])}" alt="" class="photo-hover" onerror="this.remove()">`;
  }

  // Закрашенное сердечко, если товар в избранном
  const liked = isFavorite(product.id);
  // Number(...) — id точно число, даже если в данных что-то не то
  const id = Number(product.id);

  return `
    <a href="product.html?id=${id}" class="card reveal" style="--delay: ${(index % 4) * 0.08}s">
      <div class="card-img">
        <span>${escapeHtml(product.emoji)}</span>
        ${photosHtml}
        <button type="button" class="like ${liked ? "liked" : ""}" data-id="${id}" title="В избранное">${liked ? "♥" : "♡"}</button>
      </div>
      <div class="card-brand">${escapeHtml(product.brand)}</div>
      <div class="card-title">${escapeHtml(product.title)}</div>
      <div class="card-bottom">
        <span class="card-price">${formatPrice(product.price)}</span> · <span class="card-size">${escapeHtml(product.size)}</span>
      </div>
    </a>
  `;
}

// Включает сердечки внутри сетки с карточками.
// Слушаем клик на всей сетке, а не на каждом сердечке: карточки
// перерисовываются при фильтрах, а сетка остаётся та же.
// onChange — необязательная функция, которую вызвать после клика.
function setupLikes(grid, onChange) {
  grid.addEventListener("click", (event) => {
    // closest ищет ближайший элемент с классом like: сам элемент или его родителя
    const button = event.target.closest(".like");
    if (!button) return; // кликнули не по сердечку — обычный переход на товар

    event.preventDefault(); // сердечко лежит внутри ссылки, не даём ей открыться
    const liked = toggleFavorite(Number(button.dataset.id));
    button.classList.toggle("liked", liked);
    button.textContent = liked ? "♥" : "♡";
    if (onChange) onChange();
  });
}

// ===== Управление объявлениями: кабинет и панель администратора =====

// Время из базы — UTC вида "2026-10-30 18:45:00". Добавляем "Z" (значит UTC),
// и браузер сам переведёт его в местное время
function formatDate(value) {
  return new Date(value.replace(" ", "T") + "Z")
    .toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

// Карточки объявлений с кнопкой «Снять с продажи» и раскрывающимися входящими
function renderManagedListings(grid, list) {
  // escapeHtml — тексты объявлений вставляем безопасно
  grid.innerHTML = list.map(listing => {
    const id = Number(listing.id);
    const photo = getPhotos(listing)[0];
    return `
      <div class="card" data-card="${id}">
        <a href="product.html?id=${id}">
          <div class="card-img">
            <span>${escapeHtml(listing.emoji)}</span>
            ${photo ? `<img src="${escapeHtml(photo)}" alt="">` : ""}
          </div>
          <div class="card-brand">${escapeHtml(listing.brand)}</div>
          <div class="card-title">${escapeHtml(listing.title)}</div>
          <div class="card-bottom">
            <span class="card-price">${formatPrice(listing.price)}</span> · <span class="card-size">${escapeHtml(listing.seller)}</span>
          </div>
        </a>
        <button class="btn btn-light btn-small" data-delete="${id}">Снять с продажи</button>
        <details class="inbox" data-inbox="${id}">
          <summary>Входящие</summary>
          <div class="inbox-body">Загружаем…</div>
        </details>
      </div>
    `;
  }).join("");

  grid.querySelectorAll("[data-inbox]").forEach(box => loadInbox(box));

  for (const button of grid.querySelectorAll("[data-delete]")) {
    button.onclick = async () => {
      if (!confirm("Снять это объявление с продажи? Его заказы и сообщения тоже удалятся.")) return;
      button.disabled = true;
      const response = await fetch(`/api/products/${button.dataset.delete}`, { method: "DELETE" }).catch(() => null);
      if (response?.ok) {
        document.querySelectorAll(`[data-card="${button.dataset.delete}"]`).forEach(card => card.remove());
      } else {
        alert("Не получилось снять с продажи. Попробуй ещё раз.");
        button.disabled = false;
      }
    };
  }
}

// Входящие по одному объявлению. Сервер отдаёт их только владельцу или администратору
async function loadInbox(box) {
  try {
    const response = await fetch(`/api/products/${box.dataset.inbox}/inbox`);
    if (!response.ok) throw new Error();
    const inbox = await response.json();

    const total = inbox.orders.length + inbox.offers.length + inbox.messages.length;
    box.querySelector("summary").textContent = total ? `Входящие · ${total}` : "Входящие";
    box.classList.toggle("has-new", total > 0);

    // Всё, что прислали покупатели, — через escapeHtml
    const from = item => escapeHtml(item.buyer_name || "Удалённый аккаунт");
    const rows = [
      ...inbox.orders.map(o => `<li><strong>Заказ · ${formatPrice(o.total)}</strong>
        <span>${escapeHtml(o.name)}, ${escapeHtml(o.phone)} · ${escapeHtml(o.delivery)}</span><time>${formatDate(o.created_at)}</time></li>`),
      ...inbox.offers.map(o => `<li><strong>Предложение · ${formatPrice(o.amount)}</strong>
        <span>от ${from(o)}</span><time>${formatDate(o.created_at)}</time></li>`),
      ...inbox.messages.map(m => `<li><strong>Сообщение от ${from(m)}</strong>
        <span>${escapeHtml(m.text)}</span><time>${formatDate(m.created_at)}</time></li>`)
    ];
    box.querySelector(".inbox-body").innerHTML = rows.length ? `<ul>${rows.join("")}</ul>` : "Пока ничего нет";
  } catch {
    box.querySelector(".inbox-body").textContent = "Не удалось загрузить входящие";
  }
}

// ===== Шапка: меню для телефона и поиск =====
// Шапка одинаковая на всех страницах, поэтому достраиваем её здесь,
// а не копируем одно и то же в каждый HTML-файл.
// ui.js подключён в конце body, так что шапка к этому моменту уже есть.

function setupHeader() {
  const header = document.querySelector(".header");
  const nav = header.querySelector(".nav");

  // Кнопка-«бургер» из трёх полосок. На компьютере она скрыта через CSS.
  const burger = document.createElement("button");
  burger.type = "button";
  burger.className = "burger";
  burger.title = "Меню";
  burger.innerHTML = "<span></span><span></span><span></span>";
  nav.before(burger); // ставим перед меню, в левую колонку шапки

  // Выпадающая панель: поиск + копия ссылок меню
  const menu = document.createElement("div");
  menu.className = "mobile-menu";
  menu.innerHTML = `
    <input class="search" type="text" placeholder="Поиск по брендам и вещам">
    ${nav.innerHTML}
    <a href="favorites.html">Избранное</a>
    <a href="login.html" class="account-link">Войти</a>
  `;
  // Ссылку «Войти» в шапке тоже помечаем — после входа в ней будет имя
  header.querySelector('.actions a[href="login.html"]')?.classList.add("account-link");
  header.append(menu);

  // Клик по бургеру открывает или закрывает меню
  burger.addEventListener("click", () => {
    header.classList.toggle("menu-open");
  });

  // Клик по ссылке в меню — закрываем его (важно для ссылок вида #catalog на той же странице)
  menu.addEventListener("click", (event) => {
    if (event.target.closest("a")) header.classList.remove("menu-open");
  });
}

// ===== Подвал =====
// Один и тот же на всех страницах. Чтобы добавить ссылку — допиши её сюда,
// и она появится везде сразу.
function setupFooter() {
  const footer = document.querySelector(".footer");
  if (!footer) return;
  footer.innerHTML = `
    <div class="container">
      <div class="footer-grid">
        <div>
          <a href="index.html" class="logo">RAREFORM</a>
          <p>Маркетплейс редкой, архивной и дизайнерской одежды. Каждая вещь проходит проверку подлинности.</p>
        </div>
        <div>
          <h4 class="label">Покупателям</h4>
          <ul>
            <li><a href="index.html#catalog">Каталог</a></li>
            <li><a href="designers.html">Дизайнеры</a></li>
            <li><a href="delivery.html">Доставка и оплата</a></li>
            <li><a href="favorites.html">Избранное</a></li>
          </ul>
        </div>
        <div>
          <h4 class="label">Продавцам</h4>
          <ul>
            <li><a href="sell.html">Как продать</a></li>
            <li><a href="commission.html">Комиссия</a></li>
            <li><a href="authenticity.html">Проверка подлинности</a></li>
          </ul>
        </div>
        <div>
          <h4 class="label">RAREFORM</h4>
          <ul>
            <li><a href="about.html">О нас</a></li>
            <li><a href="about.html#contacts">Контакты</a></li>
            <!-- Ведёт в личный чат Telegram, target="_blank" — в новой вкладке -->
            <li><a href="https://t.me/rostislavone1" target="_blank" rel="noopener">Telegram</a></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom label">
        © ${new Date().getFullYear()} RAREFORM · <a href="privacy.html">Политика конфиденциальности</a>
      </div>
    </div>
  `;
}

// Поиск на любой странице: Enter открывает каталог с этим запросом.
// На главной поиск работает сразу при вводе — это настроено в index.html.
function setupSearch() {
  const isCatalogPage = document.getElementById("catalog") !== null;
  for (const input of document.querySelectorAll(".search")) {
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || isCatalogPage) return;
      const text = input.value.trim();
      // encodeURIComponent — чтобы пробелы и кириллица не сломали адрес
      window.location.href = text ? `index.html?q=${encodeURIComponent(text)}#catalog` : "index.html#catalog";
    });
  }
}

// ===== Демо-версия: пометка вверху и окошко-объяснение =====

// В демо-версии в верхней чёрной полоске пишем, что это демо
productsReady.then(() => {
  if (!staticDemo) return;
  const topbar = document.querySelector(".topbar");
  if (topbar) topbar.textContent = "Демо-версия · вход, продажа и покупки работают в полной версии сайта";
});

// Маленькое окно «это демо-версия». Создаём его один раз и потом просто показываем.
// Используем те же стили .dialog, что у окон покупки
function showDemoNotice(text) {
  let dialog = document.getElementById("demo-dialog");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "demo-dialog";
    dialog.className = "dialog";
    dialog.innerHTML = `
      <span class="label">Демо-версия</span>
      <h3>Пока только витрина</h3>
      <p class="demo-text"></p>
      <button type="button" class="btn btn-dark">Понятно</button>
    `;
    dialog.querySelector("button").onclick = () => dialog.close();
    dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    document.body.append(dialog);
  }
  dialog.querySelector(".demo-text").textContent = text;
  dialog.showModal();
}

// ===== Анимации =====

// Появление при прокрутке. IntersectionObserver сам сообщает,
// когда элемент въехал в экран, — не нужно считать пиксели вручную.
const revealObserver = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
      revealObserver.unobserve(entry.target); // анимируем только один раз
    }
  }
}, { rootMargin: "0px 0px -10% 0px" }); // срабатывает чуть раньше нижнего края экрана

function watchReveal(root) {
  for (const el of root.querySelectorAll(".reveal:not(.visible)")) {
    revealObserver.observe(el);
  }
}

// Карточки каталога добавляются и перерисовываются через JavaScript.
// MutationObserver следит за страницей и отдаёт новые .reveal наблюдателю выше.
new MutationObserver(() => watchReveal(document)).observe(document.body, { childList: true, subtree: true });

// Шапка: после прокрутки на 40px получает класс scrolled (становится ниже, с тенью)
function setupHeaderScroll() {
  const header = document.querySelector(".header");
  const update = () => header.classList.toggle("scrolled", window.scrollY > 40);
  window.addEventListener("scroll", update, { passive: true });
  update();
}

// ===== Плавная прокрутка =====
// Lenis подменяет резкую прокрутку колёсиком на плавную, с инерцией.
// Если библиотека не загрузилась (нет интернета), сайт просто прокручивается обычно.
let lenis = null;

function setupSmoothScroll() {
  if (!window.Lenis) return;
  lenis = new Lenis({
    duration: 1.4, // сколько секунд «доезжает» прокрутка
    easing: t => 1 - Math.pow(1 - t, 4) // быстро в начале, мягко в конце
  });
  // Lenis двигает страницу каждый кадр. requestAnimationFrame вызывает функцию перед каждой отрисовкой
  function frame(time) {
    lenis.raf(time);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// Плавно прокрутить к элементу: через Lenis, а если его нет — встроенным способом.
// offset: -80 — останавливаемся чуть выше, чтобы элемент не спрятался под шапкой
function smoothScrollTo(element) {
  if (lenis) lenis.scrollTo(element, { offset: -80 });
  else element.scrollIntoView({ behavior: "smooth" });
}

// ===== Переходы между страницами =====
// Клик по ссылке на другую страницу: сначала страница плавно гаснет, потом открывается новая.
function setupPageTransitions() {
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link || event.defaultPrevented) return;
    // Не трогаем: ctrl/shift-клики (открыть в новой вкладке), ссылки в новое окно
    if (event.ctrlKey || event.metaKey || event.shiftKey || link.target === "_blank") return;

    const url = new URL(link.href, location.href);
    // Только ссылки на наш же сайт
    if (url.origin !== location.origin) return;
    // Ссылка внутри той же страницы (#catalog) — это не переход, а плавная прокрутка
    if (url.pathname === location.pathname && url.search === location.search) {
      const target = url.hash && document.querySelector(url.hash);
      if (target) {
        event.preventDefault();
        smoothScrollTo(target);
      }
      return;
    }

    event.preventDefault();
    document.body.classList.add("leaving");
    setTimeout(() => { location.href = url.href; }, 450); // 450 мс — как transition в CSS
  });

  // Кнопка «Назад» достаёт страницу из памяти браузера уже погашенной — включаем обратно
  window.addEventListener("pageshow", () => document.body.classList.remove("leaving"));
}

// ===== Параллакс =====
// Фото в баннере при прокрутке движется медленнее страницы — появляется ощущение глубины.
function setupParallax() {
  const heroBg = document.querySelector(".hero-bg");
  if (!heroBg) return;
  const update = () => {
    // translate — отдельное от transform свойство, поэтому не мешает анимации появления фото
    heroBg.style.translate = `0 ${window.scrollY * 0.35}px`;
  };
  window.addEventListener("scroll", update, { passive: true });
  update();
}

// ===== Кто вошёл =====
// Спрашиваем сервер. Сам токен лежит в cookie с флагом HttpOnly — JavaScript его не видит,
// браузер просто прикладывает cookie к запросу. Страницы ждут ответа так: await userReady;
let currentUser = null;

// Сначала ждём товары: так узнаём, демо это или нет. В демо сервера нет — спрашивать некого
const userReady = productsReady
  .then(() => (staticDemo ? { user: null } : fetch("/api/me").then(r => (r.ok ? r.json() : { user: null }))))
  .then(data => {
    currentUser = data.user;
    showAccountLinks();
    return currentUser;
  })
  .catch(() => null); // сервер не ответил — считаем, что никто не вошёл

// В шапке вместо «Войти» — имя и ссылка в личный кабинет
function showAccountLinks() {
  if (!currentUser) return;
  for (const link of document.querySelectorAll(".account-link")) {
    link.textContent = currentUser.name.split(" ")[0]; // только имя, без фамилии
    link.href = "account.html";
    link.title = "Личный кабинет";
  }
}

// Когда стало известно, кто вошёл, — загружаем избранное аккаунта.
// Если гость успел что-то отметить до входа, сначала переносим это в аккаунт.
// Страницы, которым нужен точный список (например «Избранное»), ждут: await favoritesReady;
const favoritesReady = userReady
  .then(async user => {
    if (!user) return; // гость — остаётся избранное из localStorage
    const guestFavorites = loadLocalFavorites();
    if (guestFavorites.length > 0) {
      // Promise.all — отправляем все запросы разом и ждём, пока выполнятся все
      await Promise.all(guestFavorites.map(id => fetch(`/api/me/favorites/${id}`, { method: "PUT" })));
      localStorage.removeItem(FAVORITES_KEY); // перенесли — в браузере больше не храним
    }
    const response = await fetch("/api/me/favorites");
    favoriteIds = new Set(response.ok ? await response.json() : []);
  })
  .catch(() => {}) // сервер не ответил — оставляем то, что было
  .then(refreshFavorites);

// Адрес страницы входа, после которой человек вернётся туда, где был
function loginUrl() {
  return `login.html?next=${encodeURIComponent(location.pathname.slice(1) + location.search)}`;
}

setupHeader();
setupFooter();
setupSearch();
setupHeaderScroll();
setupSmoothScroll();
setupPageTransitions();
setupParallax();
watchReveal(document);

// Как только товары пришли с сервера — показываем число избранного в шапке
productsReady.then(updateFavoritesCount);
