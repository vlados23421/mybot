# bot.py
import os
import random
import telebot
from telebot import types
from datetime import datetime
import database as db

# ============================================
# === НАСТРОЙКА БОТА ===
# ============================================

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.environ.get('ADMIN_IDS', '539015206').split(',')]

bot = telebot.TeleBot(TOKEN)

# ============================================
# === ОТПРАВКА КОДОВ ===
# ============================================

def generate_code():
    return str(random.randint(100000, 999999))

def send_code_to_admin(code, email, username):
    """Отправить код админу в Telegram"""
    message = f"""
🔐 **НОВЫЙ КОД ПОДТВЕРЖДЕНИЯ!**

👤 **Имя:** {username}
📧 **Email:** {email}
🔑 **Код:** `{code}`
⏱ **Действует:** 5 минут

📌 Дайте этот код пользователю для входа на сайт.
"""
    bot.send_message(ADMIN_IDS[0], message, parse_mode='Markdown')

# ============================================
# === КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    """Приветственное сообщение"""
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

---

**#BattleZ #ДоброПожаловать**
"""
    bot.send_message(message.chat.id, welcome, parse_mode='Markdown', reply_markup=keyboard)

@bot.message_handler(commands=['help'])
def help_command(message):
    """Команда помощи (без админ-команд)"""
    help_text = """
📚 **Помощь по BattleZ**

🔹 **Основные команды:**
/start — Главное меню
/help — Помощь
/profile — Мой профиль
/status — Статус проекта

📌 **Ссылки:**
🌐 Сайт: https://battle-z.vercel.app/
📱 Канал: https://t.me/StarWayBuyStarsNews

---

**#BattleZ #Помощь**
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['profile'])
def profile(message):
    """Показать профиль пользователя"""
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

---
⚔️ **BattleZ**
"""
        bot.reply_to(message, text, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Вы не зарегистрированы в боте. Напишите /start")

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
# === СКРЫТЫЕ АДМИН-КОМАНДЫ (ТОЛЬКО ДЛЯ ВАС) ===
# ============================================

@bot.message_handler(commands=['stats'])
def stats(message):
    """Статистика проекта (скрытая админ-команда)"""
    if message.from_user.id not in ADMIN_IDS:
        return  # Просто игнорируем, ничего не отвечаем
    
    total, verified = db.get_user_stats()
    bot_users = len(db.get_all_telegram_users())
    
    text = f"""
📊 **Статистика проекта**

👥 **Всего:** {total} игроков
👑 **Верифицировано:** {verified} игроков
🤖 **В боте:** {bot_users} пользователей

📅 **Запуск:** 19 августа 2026
🚀 **Версия:** 1.0.0

---
**#BattleZ #Админ #Статистика**
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['verify_user'])
def verify_user(message):
    """Выдать верификацию (скрытая админ-команда)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: /verify_user @username")
        return
    
    username = parts[1].replace('@', '')
    
    user = db.get_user_by_username(username)
    if not user:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден")
        return
    
    db.verify_user(username)
    bot.reply_to(message, f"✅ Пользователь @{username} верифицирован!")

@bot.message_handler(commands=['unverify_user'])
def unverify_user(message):
    """Отозвать верификацию (скрытая админ-команда)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: /unverify_user @username")
        return
    
    username = parts[1].replace('@', '')
    
    user = db.get_user_by_username(username)
    if not user:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден")
        return
    
    db.unverify_user(username)
    bot.reply_to(message, f"❌ Пользователь @{username} лишён верификации!")

@bot.message_handler(commands=['pending'])
def pending_users(message):
    """Список ожидающих верификации (скрытая админ-команда)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    users = db.get_all_users()
    pending = [u for u in users if not u['verified']]
    
    if not pending:
        bot.reply_to(message, "📭 Нет ожидающих верификации пользователей.")
        return
    
    text = "📋 **Ожидают верификации:**\n\n"
    for u in pending[:10]:
        text += f"👤 @{u['username']} | 📧 {u['email']} | 📅 {u['joined'].strftime('%d.%m.%Y')}\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    """Рассылка всем пользователям (скрытая админ-команда)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    text = message.text.replace('/broadcast', '').strip()
    if not text:
        bot.reply_to(message, "📝 Использование: /broadcast Текст рассылки")
        return
    
    users = db.get_all_telegram_users()
    sent = 0
    
    for user in users:
        try:
            bot.send_message(user[0], f"📢 **Уведомление от администратора:**\n\n{text}", parse_mode='Markdown')
            sent += 1
            import time
            time.sleep(0.05)
        except:
            continue
    
    bot.reply_to(message, f"✅ Рассылка отправлена {sent} пользователям!")

# ============================================
# === КОЛБЭКИ ДЛЯ КНОПОК ===
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == 'profile':
        profile(call.message)
    elif call.data == 'status':
        status(call.message)
    elif call.data == 'help':
        help_command(call.message)
    
    bot.answer_callback_query(call.id)

# ============================================
# === ЗАПУСК БОТА ===
# ============================================

if __name__ == '__main__':
    print('🤖 Бот BattleZ запущен!')
    print('📅 Дата:', datetime.now())
    print('👑 Админ ID:', ADMIN_IDS)
    print('🗄️ База данных: PostgreSQL')
    print('=' * 40)
    bot.infinity_polling()
