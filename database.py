import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_conn()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            username TEXT,
            balance DECIMAL DEFAULT 0,
            total_stars INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    # Добавляем колонку, если её ещё нет
    try:
        await conn.execute("ALTER TABLE users ADD COLUMN total_stars INTEGER DEFAULT 0")
    except Exception:
        pass
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            stars INTEGER,
            price DECIMAL,
            promo_code TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            discount DECIMAL DEFAULT 10,
            max_uses INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.close()
    print("✅ База данных инициализирована.")

async def get_user(user_id):
    conn = await get_conn()
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return user

async def register_user(user_id, username):
    conn = await get_conn()
    await conn.execute('''
        INSERT INTO users (user_id, username) VALUES ($1, $2)
        ON CONFLICT (user_id) DO NOTHING
    ''', user_id, username)
    await conn.close()

async def add_balance(user_id, amount):
    conn = await get_conn()
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)
    await conn.close()

async def get_balance(user_id):
    conn = await get_conn()
    res = await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return res or 0

async def add_purchase(user_id, stars, price, promo=None):
    conn = await get_conn()
    await conn.execute(
        "INSERT INTO purchases (user_id, stars, price, promo_code) VALUES ($1, $2, $3, $4)",
        user_id, stars, price, promo
    )
    await conn.execute("UPDATE users SET total_stars = total_stars + $1 WHERE user_id = $2", stars, user_id)
    await conn.close()

async def create_promo(code, discount, max_uses=100):
    conn = await get_conn()
    await conn.execute(
        "INSERT INTO promo_codes (code, discount, max_uses) VALUES ($1, $2, $3)",
        code, discount, max_uses
    )
    await conn.close()

async def validate_promo(code):
    conn = await get_conn()
    promo = await conn.fetchrow("SELECT * FROM promo_codes WHERE code = $1 AND active = TRUE", code)
    await conn.close()
    if not promo:
        return None
    if promo['used_count'] >= promo['max_uses']:
        return None
    return promo

async def use_promo(code):
    conn = await get_conn()
    await conn.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = $1", code)
    await conn.close()

async def get_purchases(user_id, limit=5):
    conn = await get_conn()
    rows = await conn.fetch(
        "SELECT stars, price, promo_code, created_at FROM purchases WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
        user_id, limit
    )
    await conn.close()
    return rows
