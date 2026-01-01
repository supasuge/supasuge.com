cd /home/supasuge/Documents/supasuge.com

# 1) See what you’re actually using
echo "DATABASE_URL=$DATABASE_URL"
ls -la .env || true

# 2) Confirm instance dir + perms
ls -ld instance || true
ls -la instance || true
stat -c "%A %U:%G %n" instance instance/site.db 2>/dev/null || true

# 3) If instance/ is missing, create it
mkdir -p instance
chmod 700 instance

# 4) If instance/ or DB is owned by root, fix ownership (common)
sudo chown -R "$USER:$USER" instance
chmod 700 instance

# 5) If you have leftover WAL/SHM from a bad run, remove them
rm -f instance/site.db-wal instance/site.db-shm

# 6) Ensure SECRET_KEY exists (your Config requires it)
export SECRET_KEY="dev-$(python -c 'import secrets; print(secrets.token_hex(16))')"

# 7) Run migrations (creates tables)
alembic upgrade head

# 8) Sanity check: can sqlite open it?
python - <<'PY'
import sqlite3
from pathlib import Path
p = Path("instance/site.db").resolve()
print("DB path:", p)
p.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(str(p))
conn.execute("select 1")
conn.close()
print("OK")
PY

# 9) Run app
python app.py
