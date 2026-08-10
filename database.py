import asyncpg
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_conn()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            gold INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 100,
            last_energy TIMESTAMP,
            guild_id INTEGER
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS guilds (
            id SERIAL PRIMARY KEY,
            name TEXT,
            leader_id BIGINT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS pvp_history (
            id SERIAL PRIMARY KEY,
            winner_id BIGINT,
            loser_id BIGINT,
            date TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            reward_type TEXT,
            reward_amount INTEGER,
            uses_left INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id BIGINT,
            action TEXT,
            expires_at TIMESTAMP,
            PRIMARY KEY (user_id, action)
        )
    ''')
    await conn.close()

async def get_player(user_id):
    conn = await get_conn()
    player = await conn.fetchrow("SELECT * FROM players WHERE user_id = $1", user_id)
    await conn.close()
    return player

async def create_player(user_id, username):
    conn = await get_conn()
    await conn.execute('''
        INSERT INTO players (user_id, username, last_energy)
        VALUES ($1, $2, NOW())
        ON CONFLICT (user_id) DO NOTHING
    ''', user_id, username)
    await conn.close()

async def update_player_stats(user_id, exp, gold, energy):
    conn = await get_conn()
    await conn.execute(
        "UPDATE players SET exp = exp + $1, gold = gold + $2, energy = energy - $3 WHERE user_id = $4",
        exp, gold, energy, user_id
    )
    await conn.close()

async def get_total_players():
    conn = await get_conn()
    total = await conn.fetchval("SELECT COUNT(*) FROM players")
    await conn.close()
    return total

# ===== ГИЛЬДИИ =====
async def get_guild(guild_id):
    conn = await get_conn()
    guild = await conn.fetchrow("SELECT * FROM guilds WHERE id = $1", guild_id)
    await conn.close()
    return guild

async def create_guild(name, leader_id):
    conn = await get_conn()
    guild_id = await conn.fetchval(
        "INSERT INTO guilds (name, leader_id) VALUES ($1, $2) RETURNING id",
        name, leader_id
    )
    await conn.execute("UPDATE players SET guild_id = $1 WHERE user_id = $2", guild_id, leader_id)
    await conn.close()
    return guild_id

async def get_top_guilds(limit=10):
    conn = await get_conn()
    rows = await conn.fetch("""
        SELECT g.name, COUNT(p.user_id) as members
        FROM guilds g
        LEFT JOIN players p ON p.guild_id = g.id
        GROUP BY g.id, g.name
        ORDER BY members DESC
        LIMIT $1
    """, limit)
    await conn.close()
    return rows

# ===== ПРОМОКОДЫ =====
async def create_promo_code(code, reward_type, amount, uses=1):
    conn = await get_conn()
    await conn.execute(
        "INSERT INTO promo_codes (code, reward_type, reward_amount, uses_left) VALUES ($1, $2, $3, $4)",
        code, reward_type, amount, uses
    )
    await conn.close()

async def use_promo_code(user_id, code):
    conn = await get_conn()
    promo = await conn.fetchrow("SELECT * FROM promo_codes WHERE code = $1 AND uses_left > 0", code)
    if not promo:
        await conn.close()
        return None
    player = await get_player(user_id)
    if promo['reward_type'] == 'gold':
        await conn.execute("UPDATE players SET gold = gold + $1 WHERE user_id = $2", promo['reward_amount'], user_id)
    elif promo['reward_type'] == 'exp':
        await conn.execute("UPDATE players SET exp = exp + $1 WHERE user_id = $2", promo['reward_amount'], user_id)
    await conn.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = $1", code)
    await conn.close()
    return promo

# ===== КУЛДАУНЫ =====
async def set_cooldown(user_id, action, seconds):
    conn = await get_conn()
    expires = datetime.now() + timedelta(seconds=seconds)
    await conn.execute(
        "INSERT INTO cooldowns (user_id, action, expires_at) VALUES ($1, $2, $3) ON CONFLICT (user_id, action) DO UPDATE SET expires_at = $3",
        user_id, action, expires
    )
    await conn.close()

async def check_cooldown(user_id, action):
    conn = await get_conn()
    row = await conn.fetchrow("SELECT expires_at FROM cooldowns WHERE user_id = $1 AND action = $2", user_id, action)
    await conn.close()
    if not row:
        return None
    if datetime.now() > row['expires_at']:
        return None
    return (row['expires_at'] - datetime.now()).seconds
