import os
import asyncio
import threading
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import openai  # Или любой другой AI

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # Для AI
ADMIN_IDS = [123456789]  # Ваш Telegram ID (укажите свой)
PREMIUM_PRICE = 299  # Цена в рублях (для демонстрации)

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан!")

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
app = Flask(__name__)

# --- БАЗА ДАННЫХ SQLITE ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            tickets INTEGER DEFAULT 3,
            is_premium BOOLEAN DEFAULT 0,
            premium_until TEXT,
            total_requests INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    
    # Таблица истории запросов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            answer TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица платежей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT,
            payment_id TEXT,
            created_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С БД ---
def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def create_user(user_id, username):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT OR IGNORE INTO users (user_id, username, tickets, created_at)
        VALUES (?, ?, 3, ?)
    ''', (user_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_tickets(user_id, tickets):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET tickets = ? WHERE user_id = ?', (tickets, user_id))
    conn.commit()
    conn.close()

def set_premium(user_id, days=30):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    until = (datetime.now() + timedelta(days=days)).isoformat()
    cur.execute('''
        UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?
    ''', (until, user_id))
    conn.commit()
    conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if not user:
        return False
    if user[3] == 1:  # is_premium
        if user[4] and datetime.fromisoformat(user[4]) > datetime.now():
            return True
        else:
            # Снимаем премиум если истек
            conn = sqlite3.connect('bot_database.db')
            cur = conn.cursor()
            cur.execute('UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return False
    return False

def save_history(user_id, question, answer):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO history (user_id, question, answer, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (user_id, question, answer, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# --- STATES ДЛЯ FSM ---
class Form(StatesGroup):
    waiting_for_question = State()
    waiting_for_payment = State()

# --- AI ФУНКЦИЯ ---
async def ask_ai(question, user_id):
    try:
        if not OPENAI_API_KEY:
            return "⚠️ AI не настроен. Добавьте OPENAI_API_KEY в переменные окружения."
        
        # Используем OpenAI или любой другой AI
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Вы помощник проекта BEST RUSSIA. Отвечайте на русском языке, вежливо и информативно."},
                {"role": "user", "content": question}
            ],
            max_tokens=500
        )
        answer = response.choices[0].message.content
        save_history(user_id, question, answer)
        return answer
    except Exception as e:
        return f"❌ Ошибка AI: {str(e)}"

# --- КЛАВИАТУРЫ ---
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Задать вопрос AI", callback_data="ask_ai")],
        [InlineKeyboardButton(text="🎫 Мои билеты", callback_data="my_tickets")],
        [InlineKeyboardButton(text="💎 Купить Premium", callback_data="buy_premium")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    return keyboard

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    create_user(user_id, username)
    
    welcome_text = f"""
🎯 Добро пожаловать в BEST RUSSIA!

👤 Ваш ID: {user_id}
🎫 Билетов: {get_user(user_id)[2]}
💎 Premium: {'✅ Активен' if check_premium(user_id) else '❌ Нет'}

Используйте кнопки ниже для навигации.
"""
    await message.answer(welcome_text, reply_markup=main_menu())

@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = """
📖 Помощь по боту BEST RUSSIA:

🤖 **AI-помощник** - задайте любой вопрос
🎫 **Билеты** - выдаются 3 шт. при регистрации
💎 **Premium** - безлимитный AI на 30 дней
📊 **Статистика** - ваша активность

⚠️ Каждый вопрос к AI тратит 1 билет.
Premium пользователи имеют безлимит.
"""
    await message.answer(help_text, reply_markup=main_menu())

# --- ОБРАБОТЧИКИ CALLBACK ---
@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = callback.data
    
    if data == "ask_ai":
        user = get_user(user_id)
        if not user:
            await callback.message.answer("❌ Пользователь не найден. Используйте /start")
            return
        
        tickets = user[2]
        is_premium = check_premium(user_id)
        
        if is_premium:
            await callback.message.answer("💬 Напишите ваш вопрос для AI (Premium безлимит):")
            await state.set_state(Form.waiting_for_question)
            await state.update_data(ask_type="premium")
        elif tickets > 0:
            await callback.message.answer(f"💬 Напишите ваш вопрос для AI (Осталось билетов: {tickets}):")
            await state.set_state(Form.waiting_for_question)
            await state.update_data(ask_type="ticket")
        else:
            await callback.message.answer(
                "❌ У вас закончились билеты!\n"
                "Купите Premium для безлимитного доступа.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Купить Premium", callback_data="buy_premium")]
                ])
            )
    
    elif data == "my_tickets":
        user = get_user(user_id)
        if user:
            is_premium = check_premium(user_id)
            tickets = user[2]
            text = f"""
🎫 **Ваши билеты:** {tickets}
💎 **Premium:** {'✅ Активен' if is_premium else '❌ Нет'}
📅 **Премиум до:** {user[4] if user[4] else 'Не активен'}

📊 **Всего запросов:** {user[5]}
"""
            await callback.message.answer(text, reply_markup=main_menu())
        else:
            await callback.message.answer("❌ Пользователь не найден")
    
    elif data == "buy_premium":
        text = """
💎 **Premium подписка BEST RUSSIA**

Цена: 299 ₽

✅ Безлимитные запросы к AI
✅ Приоритетная поддержка
✅ Доступ к эксклюзивным функциям

💰 Оплата: USDT (TRC20) или Telegram Stars
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Оплатить USDT", callback_data="pay_usdt")],
            [InlineKeyboardButton(text="⭐ Оплатить Stars", callback_data="pay_stars")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
    
    elif data == "pay_usdt":
        payment_id = f"BEST_{user_id}_{datetime.now().timestamp()}"
        text = f"""
💳 **Оплата через USDT (TRC20)**

Адрес для оплаты:
`TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

Сумма: 10 USDT
ID платежа: `{payment_id}`

После оплаты нажмите кнопку "✅ Я оплатил"
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"confirm_payment_{payment_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_premium")]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
    
    elif data.startswith("confirm_payment_"):
        payment_id = data.replace("confirm_payment_", "")
        # Здесь нужно проверить платеж через API криптобиржи
        # Для демонстрации сразу активируем
        set_premium(user_id, 30)
        await callback.message.answer(
            "✅ Premium активирован! Безлимитный AI теперь доступен.",
            reply_markup=main_menu()
        )
    
    elif data == "pay_stars":
        # Для Telegram Stars нужно настроить через @BotFather
        await callback.message.answer(
            "⭐ Оплата через Telegram Stars в разработке.\n"
            "Пока используйте USDT.",
            reply_markup=main_menu()
        )
    
    elif data == "stats":
        user = get_user(user_id)
        if user:
            conn = sqlite3.connect('bot_database.db')
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM history WHERE user_id = ?', (user_id,))
            total_requests = cur.fetchone()[0]
            conn.close()
            
            text = f"""
📊 **Ваша статистика**

🎫 Всего запросов: {total_requests}
💎 Premium: {'✅' if check_premium(user_id) else '❌'}
📅 Дата регистрации: {user[6][:10] if user[6] else 'Неизвестно'}
"""
            await callback.message.answer(text, reply_markup=main_menu())
    
    elif data == "help":
        await help_command(callback.message)
    
    elif data == "back":
        await callback.message.answer("Главное меню:", reply_markup=main_menu())
    
    await callback.answer()

# --- ОБРАБОТЧИК СООБЩЕНИЙ (AI) ---
@dp.message(Form.waiting_for_question)
async def handle_ai_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    question = message.text
    
    if not question:
        await message.answer("Пожалуйста, напишите текст вопроса.")
        return
    
    # Получаем данные состояния
    data = await state.get_data()
    ask_type = data.get("ask_type", "ticket")
    
    # Проверяем лимиты
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    if not is_premium and ask_type == "ticket":
        tickets = user[2]
        if tickets <= 0:
            await message.answer(
                "❌ У вас закончились билеты!\n"
                "Купите Premium для безлимитного доступа.",
                reply_markup=main_menu()
            )
            await state.clear()
            return
        # Списываем билет
        update_tickets(user_id, tickets - 1)
    
    # Отправляем статус
    waiting_msg = await message.answer("⏳ Думаю над ответом...")
    
    # Запрос к AI
    answer = await ask_ai(question, user_id)
    
    # Отправляем ответ
    await waiting_msg.delete()
    await message.answer(answer, reply_markup=main_menu())
    await state.clear()

# --- FLASK ЭНДПОИНТЫ ---
@app.route('/')
def home():
    return "🤖 BEST RUSSIA Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Для интеграции с платежными системами"""
    data = request.json
    # Обработка платежей от внешних систем
    return jsonify({"status": "ok"}), 200

@app.route('/admin/stats')
def admin_stats():
    """Статистика для админа"""
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM users')
    total_users = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    premium_users = cur.fetchone()[0]
    
    cur.execute('SELECT SUM(tickets) FROM users')
    total_tickets = cur.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        "total_users": total_users,
        "premium_users": premium_users,
        "total_tickets": total_tickets,
        "status": "running"
    })

# --- ЗАПУСК БОТА В ПОТОКЕ ---
def run_bot():
    asyncio.run(dp.start_polling(bot))

# --- ТОЧКА ВХОДА ---
if __name__ == "__main__":
    # Создаем пользователя-админа
    for admin_id in ADMIN_IDS:
        try:
            create_user(admin_id, "Admin")
            set_premium(admin_id, 365)  # Даем премиум на год
        except:
            pass
    
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
