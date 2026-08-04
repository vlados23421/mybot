import os
import asyncpg
import asyncio

# ==========================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ (ВСТАВЬ СЮДА СВОЮ ССЫЛКУ)
# ==========================================
DATABASE_URL = "postgresql://coinflow_db_user:a28Y6JFsx5AkUDbX29U57WfhCN80qXqf@dpg-d9ota5id0e5s73cbi2g0-a/coinflow_db"

# Создаём пул соединений (чтобы база не тормозила)
async def get_db():
    return await asyncpg.connect(DATABASE_URL)

# ==========================================
# ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ (Запускается один раз при старте)
# ==========================================
async def init_db():
    conn = await get_db()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            last_bonus TEXT,
            reg_date TEXT
        )
    ''')
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
            reward INTEGER,
            active INTEGER DEFAULT 1
        )
    ''')
    await conn.close()
    print("✅ База данных PostgreSQL инициализирована!")

# ==========================================
# ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
async def get_user(user_id):
    conn = await get_db()
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return user

async def register_user(user_id, username, first_name):
    conn = await get_db()
    await conn.execute('''
        INSERT INTO users (user_id, username, first_name, balance, reg_date)
        VALUES ($1, $2, $3, 0, NOW())
        ON CONFLICT (user_id) DO NOTHING
    ''', user_id, username, first_name)
    await conn.close()

async def update_bonus(user_id, today_date):
    conn = await get_db()
    await conn.execute("UPDATE users SET last_bonus = $1, balance = balance + 2500 WHERE user_id = $2", today_date, user_id)
    await conn.close()

async def get_stats():
    conn = await get_db()
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
    total_coins = await conn.fetchval("SELECT SUM(balance) FROM users") or 0
    await conn.close()
    return total_users, total_coins

# ==========================================
# ФУНКЦИИ ДЛЯ ЗАДАНИЙ
# ==========================================
async def get_all_tasks(only_active=True):
    conn = await get_db()
    if only_active:
        tasks = await conn.fetch("SELECT id, name, link, reward FROM tasks WHERE active = 1")
    else:
        tasks = await conn.fetch("SELECT id, name, link, reward FROM tasks")
    await conn.close()
    return tasks

async def get_task(task_id):
    conn = await get_db()
    task = await conn.fetchrow("SELECT id, name, link, reward FROM tasks WHERE id = $1", task_id)
    await conn.close()
    return task

async def add_task(name, link, reward):
    conn = await get_db()
    await conn.execute("INSERT INTO tasks (name, link, reward) VALUES ($1, $2, $3)", name, link, reward)
    await conn.close()

async def delete_task(task_id):
    conn = await get_db()
    await conn.execute("DELETE FROM tasks WHERE id = $1", task_id)
    await conn.close()

async def is_task_done(user_id, task_id):
    conn = await get_db()
    count = await conn.fetchval("SELECT COUNT(*) FROM completed_tasks WHERE user_id = $1 AND task_id = $2", user_id, task_id)
    await conn.close()
    return count > 0

async def mark_task_done(user_id, task_id):
    conn = await get_db()
    await conn.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES ($1, $2)", user_id, task_id)
    await conn.close()

async def add_balance(user_id, amount):
    conn = await get_db()
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)
    await conn.close()
