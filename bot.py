# bot.py
import os
import random
import telebot
from telebot import types
from datetime import datetime
import database as db  # ← Ваш файл database.py

# ============================================
# === НАСТРОЙКА БОТА ===
# ============================================

TOKEN = '8859123911:AAFE7Z6ceQIQ-JzC5xWG06YfIv21G8OaM94'
ADMIN_IDS = [539015206]  # Ваш Telegram ID

bot = telebot.TeleBot(TOKEN)

# ============================================
# === ОТПРАВКА КОДОВ ===
# ============================================

def generate_code():
    return str(random.randint(100000, 999999))

def send_code_to_admin(code, email, username):
    """Отправить код админу"""
    message = f"""
🔐 **НОВЫЙ КОД ПОДТВЕРЖДЕНИЯ!**

👤 **Имя:** {username}
📧 **Email:** {email}
🔑 **Код:** `{code}`
⏱ **Действует:** 5 минут

📌 Дайте этот код пользователю.
"""
    bot.send_message(ADMIN_IDS[0], message, parse_mode='Markdown')

def send_code_to_user(telegram_id, code):
    """Отправить код пользователю"""
    message = f"""
🔐 **Ваш код подтверждения BattleZ**

🔑 **Код:** `{code}`
⏱ **Действует:** 5 минут

🌐 https://battle-z.vercel.app/
"""
    bot.send_message(telegram_id, message, parse_mode='Markdown')

# ============================================
# === КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    """Приветствие"""
    user = db.get_telegram_user(message.from_user.id)
    
    if user is None:
        db.register_telegram_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🌐 На сайт", url="https://battle-z.vercel.app/")
    btn2 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    btn3 = types.InlineKeyboardButton("📊 Статус", callback_data="status")
    btn4 = types.InlineKeyboardButton("❓ Помощь", callback_data="help")
    keyboard.add(btn1, btn2, btn3, btn4)
    
    welcome = f"""
⚔️ **Добро пожаловать в BattleZ!**

Привет, {message.from_user.first_name}! 🎉

📌 **Что умеет бот:**
• Получать коды подтверждения
• Следить за статусом проекта
• Получать уведомления

🚀 **Присоединяйся к BattleZ!**
"""
    bot.send_message(message.chat.id, welcome, parse_mode='Markdown', reply_markup=keyboard)

@bot.message_handler(commands=['profile'])
def profile(message):
    """Показать профиль"""
    user = db.get_telegram_user(message.from_user.id)
    
    if user:
        site_user = db.get_user_by_username(user['username']) if user['username'] else None
        
        text = f"""
👤 **Ваш профиль**

👤 Имя: {user['first_name'] or 'Не указано'}
📝 Username: @{user['username'] or 'Не указан'}

**На сайте:**
{'✅ Есть аккаунт' if site_user else '❌ Нет аккаунта'}
{'👑 Верифицирован' if site_user and site_user['verified'] else ''}
"""
        bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status(message):
    """Статус проекта"""
    total, verified = db.get_user_stats()
    
    text = f"""
📊 **Статус проекта BattleZ**

👥 **Всего:** {total} игроков
👑 **Верифицировано:** {verified} игроков

🚀 **Релиз:** 19 августа 2026

---

**#BattleZ #Статус**
"""
    bot.reply_to(message, text, parse_mode='Markdown')

# ============================================
# === АДМИН-КОМАНДЫ ===
# ============================================

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Нет прав.")
        return
    
    total, verified = db.get_user_stats()
    bot_users = len(db.get_all_telegram_users())
    
    text = f"""
📊 **Статистика**

👥 Всего: {total}
👑 Верифицировано: {verified}
🤖 В боте: {bot_users}

📅 Запуск: 19.08.2026
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Нет прав.")
        return
    
    text = message.text.replace('/broadcast', '').strip()
    if not text:
        bot.reply_to(message, "📝 /broadcast Текст")
        return
    
    users = db.get_all_telegram_users()
    sent = 0
    
    for user in users:
        try:
            bot.send_message(user[0], f"📢 {text}", parse_mode='Markdown')
            sent += 1
            import time
            time.sleep(0.05)
        except:
            continue
    
    bot.reply_to(message, f"✅ Отправлено {sent} пользователям!")

@bot.message_handler(commands=['verify_user'])
def verify_user(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Нет прав.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 /verify_user @username")
        return
    
    username = parts[1].replace('@', '')
    db.verify_user(username)
    bot.reply_to(message, f"✅ @{username} верифицирован!")

@bot.message_handler(commands=['unverify_user'])
def unverify_user(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Нет прав.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 /unverify_user @username")
        return
    
    username = parts[1].replace('@', '')
    db.unverify_user(username)
    bot.reply_to(message, f"❌ @{username} лишён верификации!")

@bot.message_handler(commands=['pending'])
def pending(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Нет прав.")
        return
    
    users = db.get_all_users()
    pending_users = [u for u in users if not u['verified']]
    
    if not pending_users:
        bot.reply_to(message, "📭 Нет ожидающих.")
        return
    
    text = "📋 **Ожидают верификации:**\n\n"
    for u in pending_users[:10]:
        text += f"👤 @{u['username']} | 📧 {u['email']}\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

# ============================================
# === КОЛБЭКИ ===
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == 'profile':
        profile(call.message)
    elif call.data == 'status':
        status(call.message)
    elif call.data == 'help':
        bot.send_message(call.message.chat.id, "📚 /help — список команд", parse_mode='Markdown')
    
    bot.answer_callback_query(call.id)

# ============================================
# === ЗАПУСК ===
# ============================================

if __name__ == '__main__':
    print('🤖 Бот BattleZ запущен!')
    print('🗄️ База данных: PostgreSQL')
    print('👑 Админ ID:', ADMIN_IDS)
    print('=' * 40)
    bot.infinity_polling()
