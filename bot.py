import os
import telebot
from telebot import types
import psycopg2
import random
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

# ============================================
# === ПОДКЛЮЧЕНИЕ К POSTGRESQL (RENDER) ===
# ============================================

# Получаем URL базы данных из переменных окружения Render
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost:5432/battlez')

# Парсим URL для подключения
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# ============================================
# === НАСТРОЙКА БОТА ===
# ============================================

TOKEN = '8859123911:AAFE7Z6ceQIQ-JzC5xWG06YfIv21G8OaM94'
ADMIN_IDS = [539015206]  # Ваш Telegram ID

bot = telebot.TeleBot(TOKEN)

# ============================================
# === РАБОТА С БАЗОЙ ДАННЫХ ===
# ============================================

def init_db():
    """Создание таблиц если их нет"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Создаем таблицу для Telegram-пользователей (связь с сайтом)
    c.execute('''
        CREATE TABLE IF NOT EXISTS telegram_users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(100),
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Создаем таблицу для кодов подтверждения
    c.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(6) NOT NULL,
            email VARCHAR(100) NOT NULL,
            username VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            used BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Создаем таблицу для уведомлений
    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            message TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_to INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()
    print('✅ База данных PostgreSQL инициализирована!')

def get_user_by_telegram(telegram_id):
    """Получить пользователя по Telegram ID"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM telegram_users WHERE telegram_id = %s', (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_from_site(username):
    """Получить пользователя сайта по username"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = c.fetchone()
    conn.close()
    return user

def register_telegram_user(telegram_id, username, first_name, last_name):
    """Регистрация пользователя в боте"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO telegram_users (telegram_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name
    ''', (telegram_id, username, first_name, last_name))
    
    conn.commit()
    conn.close()

def save_verification_code(code, email, username):
    """Сохранить код подтверждения"""
    conn = get_db_connection()
    c = conn.cursor()
    
    expires_at = datetime.now() + timedelta(minutes=5)
    
    c.execute('''
        INSERT INTO verification_codes (code, email, username, expires_at)
        VALUES (%s, %s, %s, %s)
    ''', (code, email, username, expires_at))
    
    conn.commit()
    conn.close()

def verify_code(code, email):
    """Проверить код подтверждения"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT * FROM verification_codes 
        WHERE code = %s AND email = %s AND used = FALSE AND expires_at > NOW()
    ''', (code, email))
    
    result = c.fetchone()
    
    if result:
        c.execute('UPDATE verification_codes SET used = TRUE WHERE code = %s', (code,))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def get_all_telegram_users():
    """Получить всех пользователей бота"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT telegram_id FROM telegram_users')
    users = c.fetchall()
    conn.close()
    return users

def get_site_user_stats():
    """Получить статистику пользователей сайта"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE verified = TRUE')
    verified = c.fetchone()[0]
    conn.close()
    return total, verified

# ============================================
# === ОТПРАВКА КОДОВ ===
# ============================================

def generate_code():
    return str(random.randint(100000, 999999))

def send_code_to_admin(code, email, username):
    """Отправить код админу в Telegram"""
    admin_id = ADMIN_IDS[0]
    
    message = f"""
🔐 **НОВЫЙ КОД ПОДТВЕРЖДЕНИЯ!**

👤 **Имя:** {username}
📧 **Email:** {email}
🔑 **Код:** `{code}`
⏱ **Действует:** 5 минут

📌 Дайте этот код пользователю для входа на сайт.
"""
    bot.send_message(admin_id, message, parse_mode='Markdown')

def send_code_to_user(telegram_id, code):
    """Отправить код пользователю в Telegram"""
    message = f"""
🔐 **Ваш код подтверждения BattleZ**

🔑 **Код:** `{code}`
⏱ **Действует:** 5 минут

📌 Введите код на сайте для завершения регистрации.

🌐 **Перейти на сайт:** https://battle-z.vercel.app/
"""
    bot.send_message(telegram_id, message, parse_mode='Markdown')

# ============================================
# === ОБРАБОТЧИК КОМАНД ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    """Приветственное сообщение"""
    user = get_user_by_telegram(message.from_user.id)
    
    if user is None:
        register_telegram_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🌐 На сайт", url="https://battle-z.vercel.app/")
    btn2 = types.InlineKeyboardButton("📰 Новости", callback_data="news")
    btn3 = types.InlineKeyboardButton("🎮 Ивенты", callback_data="events")
    btn4 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    keyboard.add(btn1, btn2, btn3, btn4)
    
    welcome_text = f"""
⚔️ **Добро пожаловать в BattleZ!**

Привет, {message.from_user.first_name}! 🎉

BattleZ — это новый игровой проект в Telegram.

📌 **Что умеет бот:**
• Получать уведомления о новостях
• Участвовать в ивентах
• Получать коды подтверждения
• Следить за развитием проекта

🚀 **Присоединяйся к BattleZ!**

---

**#BattleZ #ДоброПожаловать**
    """
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=keyboard)

@bot.message_handler(commands=['help'])
def help_command(message):
    """Команда помощи"""
    help_text = """
📚 **Помощь по BattleZ**

🔹 **Основные команды:**
/start — Главное меню
/help — Помощь
/profile — Мой профиль
/status — Статус проекта
/verify — Проверить верификацию

🔹 **Информация:**
/support — Связаться с поддержкой

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
    user = get_user_by_telegram(message.from_user.id)
    
    if user:
        # Проверяем, есть ли пользователь на сайте
        site_user = None
        if user[2]:  # username
            site_user = get_user_from_site(user[2])
        
        profile_text = f"""
👤 **Ваш профиль**

🆔 ID: {user[1]}
👤 Имя: {user[3] or 'Не указано'}
📝 Username: @{user[2] or 'Не указан'}
📅 В боте: {user[5].strftime('%d.%m.%Y %H:%M') if user[5] else 'Неизвестно'}

**На сайте:**
{'✅ Есть аккаунт' if site_user else '❌ Нет аккаунта'}
{'👑 Верифицирован' if site_user and site_user[3] else ''}

---

⚔️ **BattleZ**
        """
        bot.reply_to(message, profile_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_command(message):
    """Статус проекта"""
    total_users, verified_users = get_site_user_stats()
    bot_users = len(get_all_telegram_users())
    
    status_text = f"""
📊 **Статус проекта BattleZ**

👥 **Всего на сайте:** {total_users} игроков
👑 **Верифицировано:** {verified_users} игроков
🤖 **В боте:** {bot_users} пользователей
🟢 **Онлайн:** ~{random.randint(10, 50)} игроков

🚀 **Текущий этап:** Оптимизация и улучшение UX
📅 **Релиз:** 19 августа 2026

---

**#BattleZ #Статус**
    """
    bot.reply_to(message, status_text, parse_mode='Markdown')

@bot.message_handler(commands=['verify'])
def verify_status(message):
    """Проверить статус верификации"""
    user = get_user_by_telegram(message.from_user.id)
    
    if user and user[2]:
        site_user = get_user_from_site(user[2])
        if site_user:
            if site_user[3]:  # verified
                bot.reply_to(message, "✅ **Вы верифицированы!** 🎉", parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ **Вы не верифицированы.** Обратитесь к администратору.", parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ **У вас нет аккаунта на сайте.** Зарегистрируйтесь!", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ **Вы не зарегистрированы в боте.** Напишите /start", parse_mode='Markdown')

# ============================================
# === АДМИН-КОМАНДЫ ===
# ============================================

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав для этой команды.")
        return
    
    total_users, verified_users = get_site_user_stats()
    bot_users = len(get_all_telegram_users())
    
    stats_text = f"""
📊 **Статистика проекта**

👥 **Пользователи сайта:** {total_users}
👑 **Верифицированы:** {verified_users}
🤖 **Пользователи бота:** {bot_users}

📅 **Запуск:** 19 августа 2026
🚀 **Версия:** 1.0.0

---

**#BattleZ #Админ #Статистика**
    """
    bot.reply_to(message, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав для этой команды.")
        return
    
    text = message.text.replace('/broadcast', '').strip()
    if not text:
        bot.reply_to(message, "📝 Использование: /broadcast Текст рассылки")
        return
    
    users = get_all_telegram_users()
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

@bot.message_handler(commands=['verify_user'])
def verify_user(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав для этой команды.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: /verify_user @username")
        return
    
    username = parts[1].replace('@', '')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET verified = TRUE WHERE username = %s', (username,))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"✅ Пользователь @{username} верифицирован!")

@bot.message_handler(commands=['unverify_user'])
def unverify_user(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав для этой команды.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: /unverify_user @username")
        return
    
    username = parts[1].replace('@', '')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET verified = FALSE WHERE username = %s', (username,))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"❌ Пользователь @{username} лишён верификации!")

@bot.message_handler(commands=['pending'])
def pending_users(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав для этой команды.")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT username, email, joined FROM users WHERE verified = FALSE ORDER BY joined DESC LIMIT 10')
    users = c.fetchall()
    conn.close()
    
    if not users:
        bot.reply_to(message, "📭 Нет ожидающих верификации пользователей.")
        return
    
    text = "📋 **Ожидают верификации:**\n\n"
    for user in users:
        text += f"👤 @{user[0]} | 📧 {user[1]} | 📅 {user[2].strftime('%d.%m.%Y')}\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

# ============================================
# === КОЛБЭКИ ДЛЯ КНОПОК ===
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == 'news':
        bot.answer_callback_query(call.id, "📰 Новости скоро появятся!")
        bot.send_message(call.message.chat.id, "📰 **Раздел новостей в разработке.**\nСледите за обновлениями!", parse_mode='Markdown')
    
    elif call.data == 'events':
        bot.answer_callback_query(call.id, "🎮 Ивенты скоро появятся!")
        bot.send_message(call.message.chat.id, "🎮 **Раздел ивентов в разработке.**\nСкоро анонсы!", parse_mode='Markdown')
    
    elif call.data == 'profile':
        profile(call.message)

# ============================================
# === ЗАПУСК БОТА ===
# ============================================

if __name__ == '__main__':
    init_db()
    print('🤖 Бот BattleZ запущен!')
    print('📅 Дата:', datetime.now())
    print('👑 Админ ID:', ADMIN_IDS)
    print('🗄️ База данных: PostgreSQL (Render)')
    print('=' * 40)
    bot.infinity_polling()
