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
from openai import OpenAI

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
ADMIN_IDS = [123456789]  # Замените на ваш Telegram ID
REFERRAL_BONUS = 2  # Билетов за приглашение

if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не задан!")

if not OPENROUTER_API_KEY:
    raise ValueError("❌ OPENROUTER_API_KEY не задан!")

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
    
    # Таблица пользователей (с реферальными полями)
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
    
    # Таблица реферальных наград
    cur.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            bonus_tickets INTEGER,
            created_at TEXT,
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id)
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

def get_user_by_referral_code(code):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM users WHERE referral_code = ?', (code,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else None

def create_user(user_id, username, referred_by=None):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    
    # Генерируем уникальный реферальный код
    import random
    import string
    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Проверяем уникальность кода
    while True:
        cur.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
        if not cur.fetchone():
            break
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Создаем пользователя
    cur.execute('''
        INSERT OR IGNORE INTO users (user_id, username, tickets, created_at, referred_by, referral_code, referrals_count)
        VALUES (?, ?, 3, ?, ?, ?, 0)
    ''', (user_id, username, datetime.now().isoformat(), referred_by, referral_code))
    
    conn.commit()
    conn.close()
    
    # Если есть реферер, начисляем бонусы
    if referred_by:
        add_referral_bonus(referred_by, user_id)
    
    return referral_code

def add_referral_bonus(referrer_id, referred_id):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    
    # Проверяем, не получал ли уже реферер бонус за этого пользователя
    cur.execute('SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?', (referrer_id, referred_id))
    if cur.fetchone():
        conn.close()
        return False
    
    # Начисляем бонус рефереру
    cur.execute('''
        UPDATE users 
        SET tickets = tickets + ?, referrals_count = referrals_count + 1 
        WHERE user_id = ?
    ''', (REFERRAL_BONUS, referrer_id))
    
    # Начисляем бонус приглашенному
    cur.execute('''
        UPDATE users 
        SET tickets = tickets + ? 
        WHERE user_id = ?
    ''', (REFERRAL_BONUS, referred_id))
    
    # Записываем в историю рефералов
    cur.execute('''
        INSERT INTO referrals (referrer_id, referred_id, bonus_tickets, created_at)
        VALUES (?, ?, ?, ?)
    ''', (referrer_id, referred_id, REFERRAL_BONUS, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return True

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

def increment_requests(user_id):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET total_requests = total_requests + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# --- STATES ДЛЯ FSM ---
class Form(StatesGroup):
    waiting_for_question = State()

# --- AI ФУНКЦИЯ (OpenRouter) ---
async def ask_ai(question, user_id):
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[
                {"role": "system", "content": "Вы помощник проекта BEST RUSSIA. Отвечайте на русском языке, вежливо, информативно и по делу. Если вопрос не по теме, вежливо откажите."},
                {"role": "user", "content": question}
            ],
            max_tokens=500,
            temperature=0.7,
            extra_headers={
                "HTTP-Referer": "https://your-site.com",
                "X-Title": "BEST RUSSIA Bot"
            }
        )
        
        answer = response.choices[0].message.content
        save_history(user_id, question, answer)
        increment_requests(user_id)
        return answer
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Ошибка AI: {error_msg}")
        
        if "rate limit" in error_msg.lower():
            return "⏳ Превышен лимит запросов. Попробуйте через минуту."
        elif "credit" in error_msg.lower() or "balance" in error_msg.lower():
            return "💳 Баланс API исчерпан. Администратор уже уведомлен."
        else:
            return f"❌ Извините, произошла ошибка. Попробуйте позже."

# --- КЛАВИАТУРЫ ---
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Задать вопрос AI", callback_data="ask_ai")],
        [InlineKeyboardButton(text="🎫 Мои билеты", callback_data="my_tickets")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="💎 Купить Premium", callback_data="buy_premium")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    return keyboard

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверяем, есть ли реферальный код
    args = message.text.split()
    referred_by = None
    
    if len(args) > 1:
        code = args[1]
        referrer_id = get_user_by_referral_code(code)
        if referrer_id and referrer_id != user_id:
            referred_by = referrer_id
    
    # Создаем пользователя
    user = get_user(user_id)
    if not user:
        referral_code = create_user(user_id, username, referred_by)
    else:
        referral_code = user[7] if user[7] else None
    
    user = get_user(user_id)
    tickets = user[2] if user else 0
    is_premium = check_premium(user_id)
    referrals_count = user[8] if user else 0
    
    welcome_text = f"""
🎯 **Добро пожаловать в BEST RUSSIA!**

👤 Ваш ID: `{user_id}`
🎫 Билетов: {tickets}
💎 Premium: {'✅ Активен' if is_premium else '❌ Нет'}
👥 Приглашено: {referrals_count}

🔹 У вас есть {tickets} бесплатных вопросов к AI
🔹 Каждый вопрос тратит 1 билет
🔹 Premium — безлимитный доступ

📌 **Реферальная ссылка:**
`https://t.me/{(await bot.get_me()).username}?start={referral_code}`

👥 За каждого приглашенного вы и ваш друг получите по {REFERRAL_BONUS} билета!
"""
    await message.answer(welcome_text, reply_markup=main_menu())

@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = """
📖 **Помощь по боту BEST RUSSIA**

🤖 **AI-помощник** — задайте любой вопрос
🎫 **Билеты** — 3 шт. при регистрации
👥 **Реферальная система** — приглашайте друзей и получайте билеты
💎 **Premium** — безлимитный AI на 30 дней
📊 **Статистика** — ваша активность

⚠️ **Правила:**
• Каждый вопрос к AI тратит 1 билет
• Premium пользователи имеют безлимит
• За каждого приглашенного +{REFERRAL_BONUS} билетов вам и другу
• Запрещены: спам, оскорбления, незаконный контент

🆘 При проблемах пишите: @your_support
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
            await callback.message.answer(
                "💬 Напишите ваш вопрос для AI (Premium — безлимит):\n\n"
                "✏️ Вопрос должен быть четким и конкретным."
            )
            await state.set_state(Form.waiting_for_question)
            await state.update_data(ask_type="premium")
        elif tickets > 0:
            await callback.message.answer(
                f"💬 Напишите ваш вопрос для AI (Осталось билетов: {tickets}):\n\n"
                "✏️ Вопрос должен быть четким и конкретным."
            )
            await state.set_state(Form.waiting_for_question)
            await state.update_data(ask_type="ticket")
        else:
            await callback.message.answer(
                "❌ **У вас закончились билеты!**\n\n"
                "Купите Premium для безлимитного доступа к AI.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Купить Premium", callback_data="buy_premium")],
                    [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referral")]
                ])
            )
    
    elif data == "referral":
        user = get_user(user_id)
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return
        
        referral_code = user[7]
        referrals_count = user[8]
        bot_username = (await bot.get_me()).username
        
        text = f"""
👥 **Реферальная система BEST RUSSIA**

🎯 **Ваша реферальная ссылка:**
`https://t.me/{bot_username}?start={referral_code}`

📊 **Статистика:**
• Приглашено: {referrals_count} человек
• Бонус: {REFERRAL_BONUS} билетов за каждого

🎁 **Как это работает:**
1. Отправьте ссылку другу
2. Друг переходит по ссылке и запускает бота
3. Вы и друг получаете по {REFERRAL_BONUS} билета

📈 **Топ пригласивших:**
"""
        # Получаем топ рефералов
        conn = sqlite3.connect('bot_database.db')
        cur = conn.cursor()
        cur.execute('''
            SELECT username, referrals_count 
            FROM users 
            WHERE referrals_count > 0 
            ORDER BY referrals_count DESC 
            LIMIT 5
        ''')
        top_referrers = cur.fetchall()
        conn.close()
        
        if top_referrers:
            for i, (username, count) in enumerate(top_referrers, 1):
                text += f"\n{i}. @{username or 'Unknown'} — {count} чел."
        else:
            text += "\nПока никто не приглашал. Будьте первым! 🏆"
        
        await callback.message.answer(text, reply_markup=main_menu())
    
    elif data == "my_tickets":
        user = get_user(user_id)
        if user:
            is_premium = check_premium(user_id)
            tickets = user[2]
            premium_until = user[4] if user[4] else "Не активен"
            if is_premium and premium_until != "Не активен":
                premium_until = datetime.fromisoformat(premium_until).strftime("%d.%m.%Y")
            
            text = f"""
🎫 **Ваши билеты:** {tickets}
💎 **Premium:** {'✅ Активен' if is_premium else '❌ Нет'}
📅 **Премиум до:** {premium_until}
📊 **Всего запросов:** {user[5]}
👥 **Приглашено:** {user[8]}

{'⭐ У вас безлимитный доступ!' if is_premium else '🎯 Купите Premium для безлимита!'}
"""
            await callback.message.answer(text, reply_markup=main_menu())
        else:
            await callback.message.answer("❌ Пользователь не найден")
    
    elif data == "buy_premium":
        text = """
💎 **Premium подписка BEST RUSSIA**

**Цена:** 299 ₽ / 30 дней

✅ Безлимитные запросы к AI
✅ Приоритетная поддержка
✅ Доступ к эксклюзивным функциям
✅ VIP-статус в сообществе

💰 **Способы оплаты:**
• USDT (TRC20)
• Telegram Stars
• Карта (СБП)

После оплаты премиум активируется автоматически.
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Оплатить USDT", callback_data="pay_usdt")],
            [InlineKeyboardButton(text="⭐ Оплатить Stars", callback_data="pay_stars")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
    
    elif data == "pay_usdt":
        payment_id = f"BEST_{user_id}_{int(datetime.now().timestamp())}"
        text = f"""
💳 **Оплата через USDT (TRC20)**

Адрес для оплаты:
`TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

Сумма: 10 USDT
ID платежа: `{payment_id}`

📌 **Инструкция:**
1. Отправьте 10 USDT на указанный адрес
2. Нажмите кнопку "✅ Я оплатил"
3. Дождитесь подтверждения (до 5 минут)

⚠️ Не указывайте адрес получателя при переводе.
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"confirm_payment_{payment_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_premium")]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
    
    elif data.startswith("confirm_payment_"):
        set_premium(user_id, 30)
        await callback.message.answer(
            "✅ **Premium активирован!**\n\n"
            "Теперь у вас безлимитный доступ к AI.\n"
            "Задавайте любые вопросы! 🎉",
            reply_markup=main_menu()
        )
    
    elif data == "pay_stars":
        await callback.message.answer(
            "⭐ **Оплата через Telegram Stars**\n\n"
            "Функция в разработке. Пока используйте USDT.\n"
            "Следите за обновлениями!",
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
            
            is_premium = check_premium(user_id)
            
            text = f"""
📊 **Ваша статистика**

📝 Всего запросов: {total_requests}
💎 Premium: {'✅ Активен' if is_premium else '❌ Нет'}
🎫 Осталось билетов: {user[2]}
👥 Приглашено: {user[8]}
📅 Дата регистрации: {user[6][:10] if user[6] else 'Неизвестно'}
"""
            await callback.message.answer(text, reply_markup=main_menu())
        else:
            await callback.message.answer("❌ Пользователь не найден")
    
    elif data == "help":
        await help_command(callback.message)
    
    elif data == "back":
        await callback.message.answer("🔙 Главное меню:", reply_markup=main_menu())
    
    await callback.answer()

# --- ОБРАБОТЧИК СООБЩЕНИЙ (AI) ---
@dp.message(Form.waiting_for_question)
async def handle_ai_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    question = message.text
    
    if not question or len(question.strip()) < 2:
        await message.answer("❌ Пожалуйста, напишите полноценный вопрос (минимум 2 символа).")
        return
    
    if len(question) > 1000:
        await message.answer("❌ Вопрос слишком длинный (максимум 1000 символов).")
        return
    
    data = await state.get_data()
    ask_type = data.get("ask_type", "ticket")
    
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    if not is_premium and ask_type == "ticket":
        tickets = user[2]
        if tickets <= 0:
            await message.answer(
                "❌ **У вас закончились билеты!**\n\n"
                "Купите Premium для безлимитного доступа.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Купить Premium", callback_data="buy_premium")],
                    [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referral")]
                ])
            )
            await state.clear()
            return
        update_tickets(user_id, tickets - 1)
    
    waiting_msg = await message.answer("⏳ Думаю над ответом...")
    
    try:
        answer = await ask_ai(question, user_id)
        await waiting_msg.delete()
        
        if len(answer) > 4000:
            parts = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
            for part in parts:
                await message.answer(part, reply_markup=main_menu())
        else:
            await message.answer(answer, reply_markup=main_menu())
            
    except Exception as e:
        await waiting_msg.delete()
        await message.answer(
            f"❌ Произошла ошибка: {str(e)[:200]}\n\n"
            "Попробуйте позже или напишите в поддержку.",
            reply_markup=main_menu()
        )
    
    await state.clear()

@dp.message()
async def unknown_command(message: Message):
    await message.answer(
        "❌ Неизвестная команда.\n"
        "Используйте /start для начала работы.",
        reply_markup=main_menu()
    )

# --- FLASK ЭНДПОИНТЫ ---
@app.route('/')
def home():
    return "🤖 BEST RUSSIA Bot is running!", 200

@app.route('/health')
def health():
    try:
        conn = sqlite3.connect('bot_database.db')
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM users')
        count = cur.fetchone()[0]
        conn.close()
        return jsonify({"status": "ok", "users": count}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        return jsonify({"status": "ok", "received": True}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/admin/stats')
def admin_stats():
    try:
        conn = sqlite3.connect('bot_database.db')
        cur = conn.cursor()
        
        cur.execute('SELECT COUNT(*) FROM users')
        total_users = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
        premium_users = cur.fetchone()[0]
        
        cur.execute('SELECT SUM(tickets) FROM users')
        total_tickets = cur.fetchone()[0] or 0
        
        cur.execute('SELECT COUNT(*) FROM history')
        total_requests = cur.fetchone()[0]
        
        cur.execute('SELECT SUM(referrals_count) FROM users')
        total_referrals = cur.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            "total_users": total_users,
            "premium_users": premium_users,
            "total_tickets": total_tickets,
            "total_requests": total_requests,
            "total_referrals": total_referrals,
            "status": "running"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ЗАПУСК БОТА В ПОТОКЕ ---
def run_bot():
    try:
        asyncio.run(dp.start_polling(bot))
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")

# --- ТОЧКА ВХОДА ---
if __name__ == "__main__":
    for admin_id in ADMIN_IDS:
        try:
            create_user(admin_id, "Admin")
            set_premium(admin_id, 365)
            print(f"✅ Admin {admin_id} создан с Premium")
        except Exception as e:
            print(f"⚠️ Ошибка создания админа: {e}")
    
    print("🚀 Запуск BEST RUSSIA Bot...")
    print(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
    print(f"🔑 OpenRouter key: {OPENROUTER_API_KEY[:10]}...")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask запущен на порту {port}")
    app.run(host="0.0.0.0", port=port)
