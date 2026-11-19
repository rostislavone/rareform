"""
Выгружает стартовые товары из базы в products.json — для демо-версии на GitHub Pages.

Там нет сервера, поэтому сайт берёт товары из этого файла.
Объявления пользователей сюда не попадают: только товары без владельца (стартовые).

Запуск из папки сайта:
    .venv\\Scripts\\python.exe export_products.py
"""

import json
from pathlib import Path

import database

products = [p for p in database.get_products() if p["user_id"] is None]
for p in products:
    p.pop("user_id")  # в демо владельцев нет

path = Path(__file__).parent / "products.json"
# ensure_ascii=False — русские буквы сохраняются как есть, а не кодами Р...
path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"products.json: {len(products)} товаров")
