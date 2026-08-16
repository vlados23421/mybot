# bot.py
import os
import sys
import random
import time
import threading
import telebot
from telebot import types
from datetime import datetime
import traceback
import database as db
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================
# === НАСТРОЙКА БОТА ===
# ============================================

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.environ.get('ADMIN_IDS', '539015206').split(',')]

print('=' * 50)
print('🚀 ЗАПУСК БОТА BATTLEZ')
print('=' * 50)
print(f'📅 Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print(f'👑 Админ ID: {ADMIN_IDS}')
print(f'🔑 Токен: {TOKEN[:15]}...' if TOKEN else '❌ ТОКЕН НЕ НАЙДЕН!')
print('=' * 50)

if not TOKEN:
    print('❌ ОШИБКА: BOT_TOKEN не найден!')
    sys.exit(1)

# ============================================
# === ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ===
# ============================================
print('🔄 Создание/проверка таблиц...')
try:
    db.init_db()
    print('✅ Таблицы готовы!')
except Exception as e:
    print(f'❌ Ошибка инициализации БД: {e}')
    sys.exit(1)

print('🔄 Проверка подключения к БД...')
try:
    stats = db.get_user_stats()
    print(f'✅ База данных работает! Пользователей: {stats[0]}')
except Exception as e:
    print(f'❌ ОШИБКА ПОДКЛЮЧЕНИЯ К БД: {e}')
    sys.exit(1)

# Создаём бота
try:
    bot = telebot.TeleBot(TOKEN)
    print('✅ Бот создан!')
except Exception as e:
    print(f'❌ ОШИБКА СОЗДАНИЯ БОТА: {e}')
    sys.exit(1)

# ============================================
# === ВЕБ-СЕРВЕР ДЛЯ ПОРТА ===
# ============================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f'✅ Веб-сервер запущен на порту {port}')
    server.serve_forever()

# ============================================
# === КОМАНДЫ БОТА ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    print(f'📩 /start от {user_id}')
    
    try:
        user = db.get_telegram_user(user_id)
        if user is None:
            db.register_telegram_user(
                user_id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            print(f'✅ Новый пользователь: {user_id}')
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton("🌐 На сайт", url="https://battle-z.vercel.app/")
        btn2 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
        btn3 = types.InlineKeyboardButton("📊 Статус", callback_data="status")
        keyboard.add(btn1, btn2, btn3)
        
        welcome = f"""
⚔️ **Добро пожаловать в BattleZ!**

Привет, {message.from_user.first_name}! 🎉

📌 Бот для управления игровым проектом.
"""
        bot.send_message(message.chat.id, welcome, parse_mode='Markdown', reply_markup=keyboard)
        
    except Exception as e:
        print(f'❌ Ошибка в /start: {e}')

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
📚 **Помощь по BattleZ**

🔹 /start — Главное меню
🔹 /help — Помощь
🔹 /profile — Мой профиль
🔹 /status — Статус проекта

🌐 Сайт: https://battle-z.vercel.app/
📱 Канал: https://t.me/StarWayBuyStarsNews
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['profile'])
def profile(message):
    try:
        user = db.get_telegram_user(message.from_user.id)
        if not user:
            bot.reply_to(message, "❌ Напишите /start")
            return
        
        site_user = db.get_user_by_username(user['username']) if user.get('username') else None
        
        text = f"""
👤 **Ваш профиль**

👤 Имя: {user.get('first_name') or 'Не указано'}
📝 Username: @{user.get('username') or 'Не указан'}

**На сайте:**
{'✅ Есть аккаунт' if site_user else '❌ Нет аккаунта'}
{'👑 Верифицирован' if site_user and site_user.get('verified') else ''}
"""
        bot.reply_to(message, text, parse_mode='Markdown')
    except Exception as e:
        print(f'❌ Ошибка /profile: {e}')

@bot.message_handler(commands=['status'])
def status(message):
    try:
        total, verified = db.get_user_stats()
        text = f"""
📊 **Статус BattleZ**

👥 Всего: {total} игроков
👑 Верифицировано: {verified}

🚀 **Релиз:** 19 августа 2026
"""
        bot.reply_to(message, text, parse_mode='Markdown')
    except Exception as e:
        print(f'❌ Ошибка /status: {e}')

# ============================================
# === СКРЫТЫЕ АДМИН-КОМАНДЫ ===
# ============================================

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        total, verified = db.get_user_stats()
        bot_users = len(db.get_all_telegram_users())
        text = f"""
📊 **Статистика**

👥 Всего: {total}
👑 Верифицировано: {verified}
🤖 В боте: {bot_users}
"""
        bot.reply_to(message, text, parse_mode='Markdown')
    except Exception as e:
        print(f'❌ Ошибка /stats: {e}')

@bot.message_handler(commands=['verify_user'])
def verify_user(message):
    if message.from_user.id not in ADMIN_IDS:
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
        return
    users = db.get_all_users()
    pending_users = [u for u in users if not u.get('verified')]
    if not pending_users:
        bot.reply_to(message, "📭 Нет ожидающих")
        return
    text = "📋 **Ожидают верификации:**\n\n"
    for u in pending_users[:10]:
        text += f"👤 @{u.get('username')} | 📧 {u.get('email')}\n"
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
    bot.answer_callback_query(call.id)

# ============================================
# === ЗАПУСК ===
# ============================================

if __name__ == '__main__':
    print('=' * 50)
    print('🤖 Бот BattleZ запускается...')
    
    # Удаляем webhook
    try:
        bot.remove_webhook()
        print('✅ Webhook удалён')
        time.sleep(2)
    except Exception as e:
        print(f'⚠️ Ошибка удаления webhook: {e}')
    
    # Запускаем веб-сервер для порта
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print(f'✅ Веб-сервер запущен на порту {os.environ.get("PORT", 10000)}')
    
    # Запускаем бота
    print('🔄 Запуск polling...')
    print('✅ Бот готов!')
    print('=' * 50)
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print('\n⏹️ Бот остановлен')
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        sys.exit(1)
