"""
Резервная копия RAREFORM: база и загруженные фото.

Запускается каждую ночь таймером rareform-backup.timer.
Копии кладутся в /srv/rareform/backups, хранятся KEEP_DAYS дней, старые удаляются.
"""

import os
import sqlite3
import tarfile
import time
from datetime import date
from pathlib import Path

DB_PATH = Path(os.environ.get("RAREFORM_DB", "/srv/rareform/data/rareform.db"))
UPLOADS = Path("/srv/rareform/images/uploads")
BACKUPS = Path("/srv/rareform/backups")
KEEP_DAYS = 14

BACKUPS.mkdir(parents=True, exist_ok=True)
today = date.today().isoformat()  # 2026-10-31

# Базу копируем встроенной командой SQLite backup, а не обычным копированием файла:
# так копия будет целой, даже если в эту секунду кто-то оформляет заказ
source = sqlite3.connect(DB_PATH)
target = sqlite3.connect(BACKUPS / f"rareform-{today}.db")
with target:
    source.backup(target)
source.close()
target.close()

# Фото упаковываем в один архив
with tarfile.open(BACKUPS / f"uploads-{today}.tar.gz", "w:gz") as archive:
    archive.add(UPLOADS, arcname="uploads")

# Удаляем копии старше KEEP_DAYS дней
limit = time.time() - KEEP_DAYS * 24 * 3600
for file in BACKUPS.iterdir():
    if file.stat().st_mtime < limit:
        file.unlink()

print("backup done:", today)
