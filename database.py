import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            # ПРИНУДИТЕЛЬНО УДАЛЯЕМ СТАРУЮ БАЗУ, ЧТОБЫ ИЗБАВИТЬСЯ ОТ ОШИБКИ OverflowError
await conn.execute("DROP TABLE IF EXISTS verify_requests")
await conn.execute("DROP TABLE IF EXISTS verified_users")
await conn.execute("DROP TABLE IF EXISTS completed_tasks")
await conn.execute("DROP TABLE IF EXISTS logs")
await conn.execute("DROP TABLE IF EXISTS tasks")
await conn.execute("DROP TABLE IF EXISTS maintenance")
await conn.execute("DROP TABLE IF EXISTS settings")
await conn.execute("DROP TABLE IF EXISTS users")
        )
    ''')
    try:
        await conn.execute("ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0")
    except Exception:
        pass
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS completed_tasks (
            user_id BIGINT,
            task_id INTEGER,
            PRIMARY KEY (user_id, task_id)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            name TEXT,
            link TEXT,
            channel_id TEXT,
            reward INTEGER,
            active INTEGER DEFAULT 1
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            action TEXT,
            details TEXT,
            time TEXT
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            bonus_amount INTEGER DEFAULT 2500
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY,
            mode INTEGER DEFAULT 0,
            message TEXT DEFAULT '⚙️ Бот на техническом обслуживании. Мы скоро вернёмся!'
        )
    ''')
    # ===== ВЕРИФИКАЦИЯ (чистая таблица) =====
    await conn.execute("DROP TABLE IF EXISTS verify_requests")
    await conn.execute('''
        CREATE TABLE verify_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            date TEXT
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS verified_users (
            user_id BIGINT PRIMARY KEY,
            verified_since TEXT,
            is_verified BOOLEAN DEFAULT FALSE
        )
    ''')
    await conn.execute('''
        INSERT INTO settings (id, bonus_amount) VALUES (1, 2500) ON CONFLICT (id) DO NOTHING
    ''')
    await conn.execute('''
        INSERT INTO maintenance (id, mode, message) VALUES (1, 0, '⚙️ Бот на техническом обслуживании. Мы скоро вернёмся!')
        ON CONFLICT (id) DO NOTHING
    ''')
    await conn.close()

async def get_user(user_id):
    conn = await get_db()
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return user

async def register_user(user_id, username, first_name):
    conn = await get_db()
    await conn.execute('''
        INSERT INTO users (user_id, username, first_name, balance, reg_date, banned)
        VALUES ($1, $2, $3, 0, NOW(), 0)
        ON CONFLICT (user_id) DO NOTHING
    ''', user_id, username, first_name)
    await conn.close()

async def add_balance(user_id, amount):
    conn = await get_db()
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)
    await conn.close()

async def get_balance(user_id):
    conn = await get_db()
    res = await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return res or 0

async def get_active_tasks():
    conn = await get_db()
    tasks = await conn.fetch("SELECT id, name, link, channel_id, reward FROM tasks WHERE active = 1")
    await conn.close()
    return tasks

async def is_task_done(user_id, task_id):
    conn = await get_db()
    res = await conn.fetchval("SELECT COUNT(*) FROM completed_tasks WHERE user_id = $1 AND task_id = $2", user_id, task_id)
    await conn.close()
    return res > 0

async def mark_task_done(user_id, task_id):
    conn = await get_db()
    await conn.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES ($1, $2)", user_id, task_id)
    await conn.close()

async def get_stats():
    conn = await get_db()
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE banned = 0")
    total_coins = await conn.fetchval("SELECT SUM(balance) FROM users") or 0
    tasks_done = await conn.fetchval("SELECT COUNT(*) FROM completed_tasks")
    await conn.close()
    return total_users, total_coins, tasks_done

async def get_all_users():
    conn = await get_db()
    users = await conn.fetch("SELECT user_id, username, first_name, balance FROM users WHERE banned = 0")
    await conn.close()
    return users

async def set_ban(user_id, ban_status):
    conn = await get_db()
    await conn.execute("UPDATE users SET banned = $1 WHERE user_id = $2", 1 if ban_status else 0, user_id)
    await conn.close()

async def is_banned(user_id):
    conn = await get_db()
    res = await conn.fetchval("SELECT banned FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return res == 1

async def add_log(user_id, action, details=""):
    conn = await get_db()
    await conn.execute("INSERT INTO logs (user_id, action, details, time) VALUES ($1, $2, $3, NOW())", user_id, action, details)
    await conn.close()

async def get_logs(limit=20):
    conn = await get_db()
    logs = await conn.fetch("SELECT * FROM logs ORDER BY id DESC LIMIT $1", limit)
    await conn.close()
    return logs

async def get_bonus_amount():
    conn = await get_db()
    res = await conn.fetchval("SELECT bonus_amount FROM settings WHERE id = 1")
    await conn.close()
    return res or 2500

async def set_bonus_amount(new_amount):
    conn = await get_db()
    await conn.execute("UPDATE settings SET bonus_amount = $1 WHERE id = 1", new_amount)
    await conn.close()

# === ТЕХРАБОТЫ ===
async def get_maintenance_mode():
    conn = await get_db()
    res = await conn.fetchval("SELECT mode FROM maintenance WHERE id = 1")
    await conn.close()
    return res == 1

async def set_maintenance_mode(status, message=None):
    conn = await get_db()
    if message:
        await conn.execute("UPDATE maintenance SET mode = $1, message = $2 WHERE id = 1", 1 if status else 0, message)
    else:
        await conn.execute("UPDATE maintenance SET mode = $1 WHERE id = 1", 1 if status else 0)
    await conn.close()

async def get_maintenance_message():
    conn = await get_db()
    res = await conn.fetchval("SELECT message FROM maintenance WHERE id = 1")
    await conn.close()
    return res or "⚙️ Бот на техническом обслуживании. Мы скоро вернёмся!"

# === ВЕРИФИКАЦИЯ ===
async def create_verify_request(user_id, username, reason):
    conn = await get_db()
    await conn.execute("INSERT INTO verify_requests (user_id, username, reason, status, date) VALUES ($1, $2, $3, 'pending', NOW())", user_id, username, reason)
    await conn.close()

async def get_pending_requests():
    conn = await get_db()
    rows = await conn.fetch("SELECT * FROM verify_requests WHERE status = 'pending'")
    await conn.close()
    return rows

async def approve_request(request_id):
    conn = await get_db()
    row = await conn.fetchrow("SELECT user_id FROM verify_requests WHERE id = $1", request_id)
    if row:
        user_id = row['user_id']
        await conn.execute("UPDATE verify_requests SET status = 'approved' WHERE id = $1", request_id)
        await conn.execute(
            "INSERT INTO verified_users (user_id, verified_since, is_verified) VALUES ($1, NOW(), TRUE) ON CONFLICT (user_id) DO UPDATE SET is_verified = TRUE",
            user_id
        )
        await conn.close()
        return user_id
    await conn.close()
    return None

async def reject_request(request_id):
    conn = await get_db()
    await conn.execute("UPDATE verify_requests SET status = 'rejected' WHERE id = $1", request_id)
    await conn.close()

async def is_user_verified(user_id):
    conn = await get_db()
    res = await conn.fetchval("SELECT is_verified FROM verified_users WHERE user_id = $1", user_id)
    await conn.close()
    return res or False

async def get_user_requests(user_id):
    conn = await get_db()
    rows = await conn.fetch("SELECT id, status, date, reason FROM verify_requests WHERE user_id = $1 ORDER BY id DESC", user_id)
    await conn.close()
    return rows
