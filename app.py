import os
import asyncio
import threading
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openai import OpenAI

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = "8428594117:AAHw06wgDdQ5rxc5SqR7gueh3l9ARVd_SCo"
OPENROUTER_API_KEY = "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"
ADMIN_IDS = [8915047087]  # ЗАМЕНИТЕ НА ВАШ ID
REFERRAL_BONUS = 2

if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не задан!")

print(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
print(f"🔑 OpenRouter key: {OPENROUTER_API_KEY[:10]}...")

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
app = Flask(__name__)

# --- OpenAI клиент для OpenRouter ---
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# --- БАЗА ДАННЫХ SQLITE ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        tickets INTEGER DEFAULT 3,
        is_premium BOOLEAN DEFAULT 0,
        premium_until TEXT,
        total_requests INTEGER DEFAULT 0,
        created_at TEXT,
        referred_by INTEGER DEFAULT NULL,
        referral_code TEXT UNIQUE,
        referrals_count INTEGER DEFAULT 0
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        question TEXT,
        answer TEXT,
        timestamp TEXT
    )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def create_user(user_id, username, referred_by=None):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    
    # Генерация реферального кода
    referral_code = f"ref{user_id}"
    
    # Время создания
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cur.execute('''
    INSERT INTO users (user_id, username, created_at, referral_code, referred_by)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, created_at, referral_code, referred_by))
    
    # Если пользователь пришел по реферальной ссылке, даем бонусы
    if referred_by and referred_by != user_id:
        # Создаем бонус в историю (упрощенно)
        cur.execute("UPDATE users SET tickets = tickets + ? WHERE user_id = ?", (REFERRAL_BONUS, user_id))
        cur.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referred_by,))
        conn.commit()
    
    conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if not user:
        return False
    # Индекс 5 - premium_until в таблице
    if user[5]:
        premium_until = datetime.strptime(user[5], "%Y-%m-%d %H:%M:%S")
        if premium_until > datetime.now():
            return True
    return False

def set_premium(user_id, days):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    premium_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (premium_until, user_id))
    conn.commit()
    conn.close()

# --- КЛАВИАТУРЫ ---
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Задать вопрос AI", callback_data="ask_ai")],
        [InlineKeyboardButton(text="🎟 Мои билеты", callback_data="my_tickets")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="💎 Купить Premium", callback_data="buy_premium")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])
    return keyboard

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    args = message.text.split()
    referred_by = None
    if len(args) > 1:
        code = args[1]
        referrer_id = get_user_by_referral_code(code)
        if referrer_id and referrer_id != user_id:
            referred_by = referrer_id

    user = get_user(user_id)
    if not user:
        create_user(user_id, username, referred_by)
    else:
        # Если пользователь уже есть, но пришел по ссылке повторно, обновляем инфо
        pass

    # Обновляем данные пользователя
    user = get_user(user_id)
    tickets = user[3] if user else 0
    is_premium = check_premium(user_id)
    referrals_count = user[8] if user else 0
    
    bot_username = (await bot.get_me()).username
    
    welcome_text = f"""
👋 **Добро пожаловать!**

🆔 Ваш ID: `{user_id}`
🎟 Билетов: `{tickets}`
💎 Premium: `{"✅ Активен" if is_premium else "❌ Нет"}`
👥 Приглашено: `{referrals_count}` чел.

🔗 **Реферальная ссылка:**
`https://t.me/{bot_username}?start={user_id}`

🎁 За каждого приглашенного вы и Ваш друг получаете по `{REFERRAL_BONUS}` билета!
"""
    await message.answer(welcome_text, reply_markup=main_menu())

@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = """
❓ **Помощь**

🤖 AI-помощник — задайте любой вопрос
🎟 Билеты — за трату при регистрации
👥 Реферальная система — приглашайте друзей
💎 Premium — безлимитный AI на 30 дней
"""
    await message.answer(help_text, reply_markup=main_menu())

# --- ЗАПУСК БОТА ---
def run_bot():
    try:
        asyncio.run(dp.start_polling(bot))
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")

if __name__ == "__main__":
    # Создаем админов
    for admin_id in ADMIN_IDS:
        try:
            create_user(admin_id, "Admin")
            set_premium(admin_id, 365)
            print(f"✅ Admin {admin_id} создан с Premium")
        except:
            pass

    print("🚀 Запуск бота...")
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask сервер
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
