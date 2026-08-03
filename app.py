import os
import sqlite3
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from openai import OpenAI

# --- ВСТАВЬТЕ СВОИ КЛЮЧИ СЮДА ---
BOT_TOKEN = "8428594117:AAHw06wgDdQ5rxc5SqR7gueh3l9ARVd_SCo"
OPENROUTER_API_KEY = "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"
ADMIN_IDS = [8915047087]
REFERRAL_BONUS = 2

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)
client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

# ========== БАЗА ДАННЫХ ==========
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

def create_user(user_id, username, referred_by=None):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    referral_code = f"ref{user_id}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute('INSERT INTO users (user_id, username, created_at, referral_code, referred_by) VALUES (?, ?, ?, ?, ?)', (user_id, username, created_at, referral_code, referred_by))
    if referred_by and referred_by != user_id:
        cur.execute("UPDATE users SET tickets = tickets + ? WHERE user_id = ?", (REFERRAL_BONUS, user_id))
        cur.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referred_by,))
        conn.commit()
    conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if not user or not user[5]: return False
    try:
        return datetime.strptime(user[5], "%Y-%m-%d %H:%M:%S") > datetime.now()
    except:
        return False

def set_premium(user_id, days):
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    premium_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (premium_until, user_id))
    conn.commit()
    conn.close()

# ========== ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЙ ==========
def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        data["reply_markup"] = keyboard
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=data)

# ========== ОБРАБОТЧИК ВЕБХУКА ==========
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" not in data:
        return "OK", 200
    
    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    user_id = msg["from"]["id"]
    username = msg["from"].get("username", "Unknown")

    # Если пользователь есть, создаем
    if not get_user(user_id):
        create_user(user_id, username)

    # ===== Команда /start =====
    if text.startswith("/start"):
        user = get_user(user_id)
        tickets = user[3] if user else 0
        is_premium = check_premium(user_id)
        referrals_count = user[8] if user else 0
        
        # Кнопки
        keyboard = {
            "inline_keyboard": [
                [{"text": "🤖 Задать вопрос AI", "callback_data": "ask_ai"}],
                [{"text": "🎟 Мои билеты", "callback_data": "my_tickets"}],
                [{"text": "👥 Реферальная система", "callback_data": "referral"}],
                [{"text": "💎 Купить Premium", "callback_data": "buy_premium"}],
                [{"text": "❓ Помощь", "callback_data": "help"}]
            ]
        }
        
        welcome_text = f"""
👋 **Добро пожаловать!**

🆔 Ваш ID: `{user_id}`
🎟 Билетов: `{tickets}`
💎 Premium: `{"✅ Активен" if is_premium else "❌ Нет"}`
👥 Приглашено: `{referrals_count}` чел.
"""
        send_message(chat_id, welcome_text, keyboard)
    
    # ===== Команда /help =====
    elif text.startswith("/help"):
        help_text = """
❓ **Помощь**

🤖 AI-помощник — задайте любой вопрос
🎟 Билеты — за трату при регистрации
👥 Реферальная система — приглашайте друзей
💎 Premium — безлимитный AI на 30 дней
"""
        send_message(chat_id, help_text)

    return "OK", 200

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print("🚀 Бот запущен и ждет сообщений!")
    app.run(host="0.0.0.0", port=port)
