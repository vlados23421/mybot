import asyncpg
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

# ===== ИНИЦИАЛИЗАЦИЯ БАЗЫ =====
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
    await conn.close()

# ===== ИГРОКИ =====
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

async def get_top_players(limit=10):
    conn = await get_conn()
    rows = await conn.fetch(
        "SELECT username, level, gold FROM players ORDER BY level DESC, gold DESC LIMIT $1",
        limit
    )
    await conn.close()
    return rows

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

async def get_guild_by_leader(leader_id):
    conn = await get_conn()
    guild = await conn.fetchrow("SELECT * FROM guilds WHERE leader_id = $1", leader_id)
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

async def join_guild(user_id, guild_id):
    conn = await get_conn()
    await conn.execute("UPDATE players SET guild_id = $1 WHERE user_id = $2", guild_id, user_id)
    await conn.close()

async def get_guild_members(guild_id):
    conn = await get_conn()
    rows = await conn.fetch("SELECT user_id, username, level FROM players WHERE guild_id = $1", guild_id)
    await conn.close()
    return rows

async def get_top_guilds(limit=10):
    conn = await get_conn()
    rows = await conn.fetch("""
        SELECT g.id, g.name, COUNT(p.user_id) as members
        FROM guilds g
        LEFT JOIN players p ON p.guild_id = g.id
        GROUP BY g.id, g.name
        ORDER BY members DESC
        LIMIT $1
    """, limit)
    await conn.close()
    return rows

# ===== PVP ИСТОРИЯ =====
async def add_pvp_battle(winner_id, loser_id):
    conn = await get_conn()
    await conn.execute(
        "INSERT INTO pvp_history (winner_id, loser_id) VALUES ($1, $2)",
        winner_id, loser_id
    )
    await conn.close()
