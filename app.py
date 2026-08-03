import os
import sqlite3
import telebot
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread  # <--- ВОТ ЭТА СТРОКА БЫЛА ПРОПУЩЕНА В ПРОШЛЫЙ РАЗ

# ===========================
# 1. ВСТАВЬТЕ СВОИ КЛЮЧИ СЮДА
# ===========================
BOT_TOKEN = "8428594117:AAHw06wgDdQ5rxc5SqR7gueh3l9ARVd_SCo"
ADMIN_ID = 8915047087  # Ваш Telegram ID
REFERRAL_BONUS = 2

bot = telebot.TeleBot(BOT_TOKEN)

# Flask - заглушка для порта Render
app = Flask(__name__)

# ===========================
# 2. БАЗА ДАННЫХ
# ===========================
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

# ===========================
# 3. КЛАВИАТУРЫ
# ===========================
def main_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("🤖 Связаться с поддержкой", callback_data="ask_ai"),
        telebot.types.InlineKeyboardButton("🎟 Мои билеты", callback_data="my_tickets"),
        telebot.types.InlineKeyboardButton("👥 Реферальная система", callback_data="referral"),
        telebot.types.InlineKeyboardButton("💎 Купить Premium", callback_data="buy_premium"),
        telebot.types.InlineKeyboardButton("❓ Помощь", callback_data="help")
    )
    return markup

# ===========================
# 4. ОБРАБОТЧИКИ КОМАНД
# ===========================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    args = message.text.split()
    referred_by = None
    if len(args) > 1:
        code = args[1]
        if code.isdigit() and int(code) != user_id:
            referred_by = int(code)

    if not get_user(user_id):
        create_user(user_id, username, referred_by)
    
    user = get_user(user_id)
    tickets = user[3] if user else 0
    is_premium = check_premium(user_id)
    referrals_count = user[8] if user else 0
    
    welcome_text = f"""
👋 **Добро пожаловать!**

🆔 Ваш ID: `{user_id}`
🎟 Билетов: `{tickets}`
💎 Premium: `{"✅ Активен" if is_premium else "❌ Нет"}`
👥 Приглашено: `{referrals_count}` чел.
"""
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.send_message(message.chat.id, "❓ **Помощь:**\n🤖 Поддержка - задайте вопрос\n🎟 Билеты - ваш баланс\n👥 Рефералы - получайте билеты", reply_markup=main_menu())

# ===========================
# 5. ОБРАБОТЧИКИ КНОПОК
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "ask_ai":
        bot.send_message(call.message.chat.id, "🤖 **Поддержка.** Напишите ваш вопрос, и я перешлю его администратору.")
    
    elif call.data == "my_tickets":
        user = get_user(call.from_user.id)
        tickets = user[3] if user else 0
        bot.send_message(call.message.chat.id, f"🎟 **Ваши билеты:** `{tickets}`", parse_mode="Markdown")
        
    elif call.data == "referral":
        bot.send_message(call.message.chat.id, f"👥 Приглашайте друзей по вашей ссылке, чтобы получать билеты!")
        
    elif call.data == "buy_premium":
        bot.send_message(call.message.chat.id, "💎 Функция Premium пока в разработке.")
        
    elif call.data == "help":
        bot.send_message(call.message.chat.id, "❓ **Помощь:**\n🤖 Поддержка - задайте вопрос\n🎟 Билеты - ваш баланс\n👥 Рефералы - получайте билеты")

# ===========================
# 6. ОБРАБОТЧИК ТЕКСТА (Пересылка админу)
# ===========================
@bot.message_handler(func=lambda message: True)
def forward_to_admin(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    text = message.text
    
    user = get_user(user_id)
    tickets = user[3] if user else 0
    
    if tickets <= 0:
        bot.send_message(user_id, "❌ У вас закончились билеты. Обратитесь к администратору.")
        return

    forward_msg = f"""
✉️ **Новое обращение от пользователя**

👤 ID: `{user_id}`
👤 Username: @{username}
🎟 Билетов: `{tickets}`

📝 **Вопрос:**
{text}
"""
    bot.send_message(ADMIN_ID, forward_msg, parse_mode="Markdown")
    
    # Списание билета
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    cur.execute("UPDATE users SET tickets = tickets - 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    bot.send_message(user_id, "✅ Ваш вопрос отправлен администратору. Ожидайте ответа.")

# ===========================
# 7. ЗАПУСК
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    # Запускаем бота в отдельном потоке
    print("🚀 Запуск бота на telebot...")
    Thread(target=bot.infinity_polling, daemon=True).start()
    
    # Держим порт открытым для Render
    app.run(host="0.0.0.0", port=port)
