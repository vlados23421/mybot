import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from openai import OpenAI

# ==========================================
# 1. ВСТАВЬТЕ СВОИ КЛЮЧИ СЮДА
# ==========================================
BOT_TOKEN = "8428594117:AAHw06wgDdQ5rxc5SqR7gueh3l9ARVd_SCo" 
OPENROUTER_API_KEY = "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"
ADMIN_IDS = [8915047087] 
REFERRAL_BONUS = 2

# ==========================================
# 2. ИНИЦИАЛИЗАЦИЯ
# ==========================================
app_flask = Flask(__name__) # Переименовали, чтобы не путать с Application

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ==========================================
# 3. БАЗА ДАННЫХ (Полностью скопирована с прошлого раза)
# ==========================================
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

def get_user_by_referral_code(code):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
    result = cur.fetchone()
    conn.close()
    if result:
        return result[0]
    return None

def create_user(user_id, username, referred_by=None):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    referral_code = f"ref{user_id}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute('''
    INSERT INTO users (user_id, username, created_at, referral_code, referred_by)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, created_at, referral_code, referred_by))
    
    if referred_by and referred_by != user_id:
        cur.execute("UPDATE users SET tickets = tickets + ? WHERE user_id = ?", (REFERRAL_BONUS, user_id))
        cur.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referred_by,))
        conn.commit()
    conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if not user:
        return False
    if user[5]:
        try:
            premium_until = datetime.strptime(user[5], "%Y-%m-%d %H:%M:%S")
            if premium_until > datetime.now():
                return True
        except:
            return False
    return False

def set_premium(user_id, days):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    premium_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (premium_until, user_id))
    conn.commit()
    conn.close()

# ==========================================
# 4. КЛАВИАТУРЫ И ОБРАБОТЧИКИ (Новый синтаксис)
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    args = context.args
    referred_by = None
    if args:
        code = args[0]
        referrer_id = get_user_by_referral_code(code)
        if referrer_id and referrer_id != user_id:
            referred_by = referrer_id

    user = get_user(user_id)
    if not user:
        create_user(user_id, username, referred_by)
    
    user = get_user(user_id)
    tickets = user[3] if user else 0
    is_premium = check_premium(user_id)
    referrals_count = user[8] if user else 0
    
    bot_user = await context.bot.get_me()
    bot_username = bot_user.username
    
    welcome_text = f"""
👋 **Добро пожаловать!**

🆔 Ваш ID: `{user_id}`
🎟 Билетов: `{tickets}`
💎 Premium: `{"✅ Активен" if is_premium else "❌ Нет"}`
👥 Приглашено: `{referrals_count}` чел.

🔗 **Реферальная ссылка:**
`https://t.me/{bot_username}?start={user_id}`
"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Задать вопрос AI", callback_data="ask_ai")],
        [InlineKeyboardButton("🎟 Мои билеты", callback_data="my_tickets")],
        [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton("💎 Купить Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ])
    await update.message.reply_text(welcome_text, reply_markup=keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Задать вопрос AI", callback_data="ask_ai")],
        [InlineKeyboardButton("🎟 Мои билеты", callback_data="my_tickets")],
        [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton("💎 Купить Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ])
    help_text = """
❓ **Помощь**

🤖 AI-помощник — задайте любой вопрос
🎟 Билеты — за трату при регистрации
👥 Реферальная система — приглашайте друзей
💎 Premium — безлимитный AI на 30 дней
"""
    await update.message.reply_text(help_text, reply_markup=keyboard)

# ==========================================
# 5. ЗАПУСК
# ==========================================
if __name__ == "__main__":
    for admin_id in ADMIN_IDS:
        try:
            create_user(admin_id, "Admin")
            set_premium(admin_id, 365)
            print(f"✅ Admin {admin_id} создан с Premium")
        except:
            pass

    print("🚀 Запуск бота...")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Запускаем бота (Polling через Flask в фоне)
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port) # Это заглушка для Render
    
    # Реальный запуск бота
    application.run_polling()
