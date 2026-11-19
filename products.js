// ===== Список всех товаров =====
// Товары теперь хранятся на сервере, в базе данных rareform.db
// (начальные данные — в database.py). Здесь мы их только загружаем.
//
// Загрузка из интернета занимает время, поэтому сначала список пустой.
// productsReady — «обещание» (Promise): оно выполнится, когда товары придут.
// Страницы ждут его так: await productsReady;

const products = [];

// ===== Демо-версия =====
// На GitHub Pages нет нашего Python-сервера — там лежат только файлы.
// Тогда товары берём из файла products.json (копия стартовых товаров из базы),
// а вход, «Продать» и покупки показывают «это демо-версия».
// staticDemo станет true, если сервер не ответил, а файл products.json нашёлся.
let staticDemo = false;

const productsReady = fetch("/api/products")
  .then(response => {
    if (!response.ok) throw new Error("Сервер ответил ошибкой " + response.status);
    return response.json(); // ответ сервера — текст в формате JSON, превращаем его в массив
  })
  .catch(() =>
    // Сервера нет — пробуем файл. Путь без "/" в начале: на GitHub Pages сайт лежит
    // не в корне, а в папке репозитория (ник.github.io/rareform/)
    fetch("products.json").then(response => {
      if (!response.ok) throw new Error("Нет ни сервера, ни products.json");
      staticDemo = true;
      return response.json();
    })
  )
  .then(list => {
    products.push(...list);
    return products;
  })
  .catch(error => {
    // Сервер не запущен или нет связи — показываем подсказку, список остаётся пустым
    console.error("Не удалось загрузить товары:", error);
    showServerNotice();
    return products;
  });

// Полоска сверху страницы, если товары не загрузились.
// Чаще всего это значит, что сайт открыт двойным кликом по файлу (адрес file:///...),
// а не через сервер (адрес http://localhost:5500).
function showServerNotice() {
  const notice = document.createElement("div");
  notice.className = "server-notice";
  notice.textContent = location.protocol === "file:"
    ? "Сайт открыт как файл, поэтому товары не загрузились. Запусти сервер и открой http://localhost:5500"
    : "Не удалось загрузить товары: сервер не отвечает. Проверь, что он запущен.";
  document.body.prepend(notice);
}

// ===== Дизайнеры =====
// Объект, где ключ — название бренда (точно как в поле brand у товаров),
// а значение — информация о нём. Если бренда здесь нет (например, его
// добавили через «Продать»), он всё равно появится на странице дизайнеров,
// просто без страны и описания.

const designers = {
  "Rick Owens":        { country: "США",      about: "Тёмный авангард, драпировки и фирменные кроссовки Geobasket." },
  "Maison Margiela":   { country: "Франция",  about: "Деконструкция, анонимность и белые стежки на спине." },
  "Raf Simons":        { country: "Бельгия",  about: "Молодёжные субкультуры, архивные коллекции 2000-х." },
  "Gucci":             { country: "Италия",   about: "Итальянская роскошь с 1921 года, Horsebit и монограмма GG." },
  "Supreme":           { country: "США",      about: "Скейт-бренд из Нью-Йорка, Box Logo и коллаборации." },
  "Guidi":             { country: "Италия",   about: "Обувь ручной работы из лошадиной кожи с окраской в бочках." },
  "Comme des Garçons": { country: "Япония",   about: "Рей Кавакубо: асимметрия, чёрный цвет и эксперименты с формой." },
  "Yohji Yamamoto":    { country: "Япония",   about: "Объёмный чёрный крой и поэзия несовершенства." },
  "Undercover":        { country: "Япония",   about: "Дзюн Такахаси: панк, графика и культовые архивные сезоны." }
};



// Превращает число 92999 в строку «92 999 ₽»
function formatPrice(price) {
  return price.toLocaleString("ru-RU") + " ₽";
}

// ===== Фото товаров =====
// Фото лежат в папке images, а у каждого товара в поле photos
// записаны имена его файлов. Первое фото — главное.
// Если у товара нет фото, вместо него показывается эмодзи.
function getPhotos(product) {
  const photos = product.photos || []; // || [] — если поля photos нет, берём пустой список
  // Фото из формы «Продать» сервер кладёт в images/uploads/, поэтому путь у всех одинаковый
  return photos.map(name => "images/" + name);
}
