import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

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
            channel_id TEXT,
            reward INTEGER,
            active INTEGER DEFAULT 1
        )
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
        INSERT INTO users (user_id, username, first_name, balance, reg_date)
        VALUES ($1, $2, $3, 0, NOW())
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
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
    total_coins = await conn.fetchval("SELECT SUM(balance) FROM users") or 0
    await conn.close()
    return total_users, total_coins
