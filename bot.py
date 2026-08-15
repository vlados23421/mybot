# bot.py
import os
import sys
import random
import time
import telebot
from telebot import types
from datetime import datetime
import traceback

# ============================================
# === ИМПОРТ БАЗЫ ДАННЫХ ===
# ============================================
try:
    import database as db
    print('✅ database.py загружен')
except ImportError as e:
    print(f'❌ Ошибка импорта database.py: {e}')
    sys.exit(1)

# ============================================
# === НАСТРОЙКА БОТА ===
# ============================================

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = []

# Получаем ADMIN_IDS из переменной окружения
admin_ids_str = os.environ.get('ADMIN_IDS', '539015206')
try:
    ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
except ValueError:
    print(f'❌ Ошибка: ADMIN_IDS должен содержать числа, получено: {admin_ids_str}')
    sys.exit(1)

print('=' * 50)
print('🚀 ЗАПУСК БОТА BATTLEZ')
print('=' * 50)
print(f'📅 Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print(f'👑 Админ ID: {ADMIN_IDS}')
print(f'🔑 Токен: {TOKEN[:15]}...' if TOKEN else '❌ ТОКЕН НЕ НАЙДЕН!')
print('=' * 50)

# Проверка токена
if not TOKEN:
    print('❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!')
    print('📌 Добавьте BOT_TOKEN в Environment Variables на Render')
    sys.exit(1)

# Проверка подключения к БД
print('🔄 Проверка подключения к базе данных...')
try:
    stats = db.get_user_stats()
    print(f'✅ База данных работает! Пользователей: {stats[0]}')
except Exception as e:
    print(f'❌ ОШИБКА ПОДКЛЮЧЕНИЯ К БД: {e}')
    traceback.print_exc()
    print('📌 Проверьте DATABASE_URL в Environment Variables')
    sys.exit(1)

# Создаём бота
try:
    bot = telebot.TeleBot(TOKEN)
    print('✅ Бот создан!')
except Exception as e:
    print(f'❌ ОШИБКА СОЗДАНИЯ БОТА: {e}')
    sys.exit(1)

# ============================================
# === ОТПРАВКА КОДОВ ===
# ============================================

def generate_code():
    """Генерация 6-значного кода"""
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
    try:
        bot.send_message(ADMIN_IDS[0], message, parse_mode='Markdown')
        print(f'✅ Код {code} отправлен админу')
        return True
    except Exception as e:
        print(f'❌ Ошибка отправки админу: {e}')
        return False

def send_code_to_user(telegram_id, code):
    """Отправить код пользователю"""
    message = f"""
🔐 **Ваш код подтверждения BattleZ**

🔑 **Код:** `{code}`
⏱ **Действует:** 5 минут

🌐 https://battle-z.vercel.app/
"""
    try:
        bot.send_message(telegram_id, message, parse_mode='Markdown')
        print(f'✅ Код {code} отправлен пользователю {telegram_id}')
        return True
    except Exception as e:
        print(f'❌ Ошибка отправки пользователю: {e}')
        return False

# ============================================
# === КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    """Приветственное сообщение"""
    user_id = message.from_user.id
    print(f'📩 Получена команда /start от {user_id}')
    
    try:
        # Регистрация пользователя в боте
        user = db.get_telegram_user(user_id)
        
        if user is None:
            db.register_telegram_user(
                user_id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            print(f'✅ Новый пользователь зарегистрирован: {user_id}')
        
        # Клавиатура
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton("🌐 На сайт", url="https://battle-z.vercel.app/")
        btn2 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
        btn3 = types.InlineKeyboardButton("📊 Статус", callback_data="status")
        btn4 = types.InlineKeyboardButton("❓ Помощь", callback_data="help")
        keyboard.add(btn1, btn2, btn3, btn4)
        
        # Приветствие
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
        print(f'✅ Приветствие отправлено пользователю {user_id}')
        
    except Exception as e:
        print(f'❌ Ошибка в /start: {e}')
        traceback.print_exc()
        try:
            bot.reply_to(message, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass

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

📌 **Ссылки:**
🌐 Сайт: https://battle-z.vercel.app/
📱 Канал: https://t.me/StarWayBuyStarsNews
"""
    try:
        bot.reply_to(message, help_text, parse_mode='Markdown')
    except Exception as e:
        print(f'❌ Ошибка в /help: {e}')

@bot.message_handler(commands=['profile'])
def profile(message):
    """Показать профиль пользователя"""
    user_id = message.from_user.id
    print(f'📩 Получена команда /profile от {user_id}')
    
    try:
        user = db.get_telegram_user(user_id)
        
        if not user:
            bot.reply_to(message, "❌ Вы не зарегистрированы в боте. Напишите /start")
            return
        
        # Проверяем наличие аккаунта на сайте
        site_user = None
        if user.get('username'):
            site_user = db.get_user_by_username(user['username'])
        
        text = f"""
👤 **Ваш профиль**

👤 Имя: {user.get('first_name') or 'Не указано'}
📝 Username: @{user.get('username') or 'Не указан'}

**На сайте:**
{'✅ Есть аккаунт' if site_user else '❌ Нет аккаунта'}
{'👑 Верифицирован' if site_user and site_user.get('verified') else ''}

---
⚔️ **BattleZ**
"""
        bot.reply_to(message, text, parse_mode='Markdown')
        
    except Exception as e:
        print(f'❌ Ошибка в /profile: {e}')
        traceback.print_exc()
        try:
            bot.reply_to(message, "❌ Произошла ошибка")
        except:
            pass

@bot.message_handler(commands=['status'])
def status(message):
    """Статус проекта"""
    print(f'📩 Получена команда /status от {message.from_user.id}')
    
    try:
        total, verified = db.get_user_stats()
        
        text = f"""
📊 **Статус проекта BattleZ**

👥 **Всего:** {total} игроков
👑 **Верифицировано:** {verified} игроков

🚀 **Релиз:** 19 августа 2026
"""
        bot.reply_to(message, text, parse_mode='Markdown')
        
    except Exception as e:
        print(f'❌ Ошибка в /status: {e}')
        traceback.print_exc()
        try:
            bot.reply_to(message, "❌ Произошла ошибка")
        except:
            pass

# ============================================
# === СКРЫТЫЕ АДМИН-КОМАНДЫ ===
# ============================================

@bot.message_handler(commands=['stats'])
def stats(message):
    """Статистика (только для админа)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    print(f'📩 Админ-команда /stats от {message.from_user.id}')
    
    try:
        total, verified = db.get_user_stats()
        bot_users = len(db.get_all_telegram_users())
        
        text = f"""
📊 **СТАТИСТИКА ПРОЕКТА**

👥 **Всего:** {total} игроков
👑 **Верифицировано:** {verified} игроков
🤖 **В боте:** {bot_users} пользователей

📅 **Запуск:** 19 августа 2026
"""
        bot.reply_to(message, text, parse_mode='Markdown')
        
    except Exception as e:
        print(f'❌ Ошибка в /stats: {e}')
        try:
            bot.reply_to(message, "❌ Ошибка получения статистики")
        except:
            pass

@bot.message_handler(commands=['verify_user'])
def verify_user(message):
    """Выдать верификацию (только для админа)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    print(f'📩 Админ-команда /verify_user от {message.from_user.id}')
    
    try:
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
        
    except Exception as e:
        print(f'❌ Ошибка в /verify_user: {e}')
        try:
            bot.reply_to(message, "❌ Ошибка")
        except:
            pass

@bot.message_handler(commands=['unverify_user'])
def unverify_user(message):
    """Отозвать верификацию (только для админа)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    print(f'📩 Админ-команда /unverify_user от {message.from_user.id}')
    
    try:
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
        
    except Exception as e:
        print(f'❌ Ошибка в /unverify_user: {e}')
        try:
            bot.reply_to(message, "❌ Ошибка")
        except:
            pass

@bot.message_handler(commands=['pending'])
def pending_users(message):
    """Список ожидающих верификации (только для админа)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    print(f'📩 Админ-команда /pending от {message.from_user.id}')
    
    try:
        users = db.get_all_users()
        pending = [u for u in users if not u.get('verified')]
        
        if not pending:
            bot.reply_to(message, "📭 Нет ожидающих верификации пользователей.")
            return
        
        text = "📋 **Ожидают верификации:**\n\n"
        for u in pending[:10]:
            joined = u.get('joined')
            if joined:
                joined_str = joined.strftime('%d.%m.%Y') if hasattr(joined, 'strftime') else str(joined)[:10]
            else:
                joined_str = 'неизвестно'
            text += f"👤 @{u.get('username')} | 📧 {u.get('email')} | 📅 {joined_str}\n"
        
        bot.reply_to(message, text, parse_mode='Markdown')
        
    except Exception as e:
        print(f'❌ Ошибка в /pending: {e}')
        try:
            bot.reply_to(message, "❌ Ошибка")
        except:
            pass

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    """Рассылка всем пользователям (только для админа)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    print(f'📩 Админ-команда /broadcast от {message.from_user.id}')
    
    try:
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
                time.sleep(0.05)
            except Exception as e:
                print(f'⚠️ Не удалось отправить пользователю {user[0]}: {e}')
                continue
        
        bot.reply_to(message, f"✅ Рассылка отправлена {sent} пользователям!")
        
    except Exception as e:
        print(f'❌ Ошибка в /broadcast: {e}')
        try:
            bot.reply_to(message, "❌ Ошибка рассылки")
        except:
            pass

# ============================================
# === КОЛБЭКИ ДЛЯ КНОПОК ===
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    print(f'📩 Получен callback: {call.data} от {call.from_user.id}')
    
    try:
        if call.data == 'profile':
            profile(call.message)
        elif call.data == 'status':
            status(call.message)
        elif call.data == 'help':
            help_command(call.message)
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f'❌ Ошибка в callback: {e}')
        try:
            bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
        except:
            pass

# ============================================
# === ОБРАБОТЧИК ОШИБОК ===
# ============================================

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """Ответ на неизвестные сообщения"""
    bot.reply_to(message, "❌ Неизвестная команда. Напишите /help для списка команд.")

# ============================================
# === ЗАПУСК БОТА ===
# ============================================

if __name__ == '__main__':
    print('=' * 50)
    print('🤖 Бот BattleZ запускается...')
    print('📅 Дата:', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('👑 Админ ID:', ADMIN_IDS)
    print('🗄️ База данных: PostgreSQL')
    print('=' * 50)
    
    # Удаляем webhook перед запуском
    try:
        bot.remove_webhook()
        print('✅ Webhook удалён')
        time.sleep(1)
    except Exception as e:
        print(f'⚠️ Ошибка удаления webhook: {e}')
    
    # Запускаем бота
    print('🔄 Запуск polling...')
    print('✅ Бот готов к работе!')
    print('=' * 50)
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print('\n⏹️ Бот остановлен пользователем')
    except Exception as e:
        print(f'❌ КРИТИЧЕСКАЯ ОШИБКА: {e}')
        traceback.print_exc()
        sys.exit(1)
