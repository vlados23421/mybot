import telebot
from telebot import types
import os
import time
import logging
from datetime import datetime
from flask import Flask
import threading
import json

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ Ошибка: BOT_TOKEN или CHANNEL_ID не заданы!")
    exit(1)

# ===== FLASK APP =====
app = Flask(__name__)

@app.route('/')
def index():
    return "🤖 VIBE RUSSIA Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

# ===== TELEGRAM BOT =====
bot = telebot.TeleBot(BOT_TOKEN)

# ===== ХРАНИЛИЩЕ СОСТОЯНИЙ (в памяти) =====
user_states = {}  # {user_id: {'state': 'helper_name', 'data': {...}}}
user_data = {}    # {user_id: {'name': '...', 'age': '...', ...}}

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def send_to_channel(app_type, text, user_id, user_name=None):
    try:
        header = f"📩 НОВАЯ ЗАЯВКА: {app_type}\n"
        header += f"👤 От: @{user_name or user_id}\n"
        header += f"🆔 ID: {user_id}\n"
        header += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        bot.send_message(CHANNEL_ID, header + text)
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🙋‍♂️ Стать Хелпером")
    btn2 = types.KeyboardButton("🛠 Техподдержка")
    btn3 = types.KeyboardButton("⚠️ Подать жалобу")
    btn4 = types.KeyboardButton("ℹ️ О боте")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

def get_cancel_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))
    return markup

def get_state(user_id):
    """Получить текущее состояние пользователя"""
    return user_states.get(str(user_id))

def set_state(user_id, state):
    """Установить состояние пользователя"""
    user_states[str(user_id)] = state
    if state not in user_data:
        user_data[str(user_id)] = {}

def clear_state(user_id):
    """Очистить состояние пользователя"""
    if str(user_id) in user_states:
        del user_states[str(user_id)]
    if str(user_id) in user_data:
        del user_data[str(user_id)]

def get_data(user_id):
    """Получить данные пользователя"""
    return user_data.get(str(user_id), {})

def set_data(user_id, key, value):
    """Установить данные пользователя"""
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    user_data[str(user_id)][key] = value

def is_cancel(text):
    return text and text in ["❌ Отмена", "Отмена", "/cancel"]

# ============================================
# ===== КОМАНДЫ =====
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    clear_state(message.from_user.id)
    user_name = message.from_user.first_name
    welcome_text = (
        f"🎮 *Добро пожаловать в VIBE RUSSIA!*\n\n"
        f"👋 Привет, {user_name}!\n"
        f"Я помогу тебе взаимодействовать с командой проекта.\n\n"
        f"📌 *Что я умею:*\n"
        f"• 🙋‍♂️ Принимать заявки на Хелпера\n"
        f"• 🛠 Принимать обращения в техподдержку\n"
        f"• ⚠️ Принимать жалобы на участников\n\n"
        f"👇 *Выбери нужный пункт в меню ниже:*"
    )
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 *Помощь по боту VIBE RUSSIA*\n\n"
        "🙋‍♂️ *Стать Хелпером* — заполни анкету\n"
        "🛠 *Техподдержка* — сообщи о проблеме\n"
        "⚠️ *Подать жалобу* — сообщи о нарушении\n\n"
        "❌ *Отмена* — отменить текущее действие"
    )
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

@bot.message_handler(commands=['cancel'])
def cancel(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "❌ Действие отменено.",
        reply_markup=get_main_menu()
    )

# ============================================
# ===== КНОПКИ МЕНЮ =====
# ============================================
@bot.message_handler(func=lambda msg: msg.text == "🙋‍♂️ Стать Хелпером")
def start_helper(message):
    set_state(message.from_user.id, 'helper_name')
    bot.send_message(
        message.chat.id,
        "📝 *Заявка на Хелпера*\n\nВведите ваши *Имя и Фамилию*:",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "🛠 Техподдержка")
def start_support(message):
    set_state(message.from_user.id, 'support_problem')
    bot.send_message(
        message.chat.id,
        "🔧 *Обращение в техподдержку*\n\nОпишите проблему. Можно приложить скриншот.",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "⚠️ Подать жалобу")
def start_complain(message):
    set_state(message.from_user.id, 'complain_against')
    bot.send_message(
        message.chat.id,
        "⚠️ *Подача жалобы*\n\nУкажите ник или ID человека:",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ О боте")
def about(message):
    about_text = (
        "🤖 *VIBE RUSSIA Bot*\n\n"
        "Версия: 2.0\n"
        "Для проекта VIBE RUSSIA\n\n"
        "📌 *Назначение:*\n"
        "• Прием заявок на Хелперов\n"
        "• Обработка обращений в техподдержку\n"
        "• Прием жалоб"
    )
    bot.send_message(
        message.chat.id,
        about_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "❌ Отмена")
def cancel_action(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "❌ Действие отменено.",
        reply_markup=get_main_menu()
    )

# ============================================
# ===== ОБРАБОТКА СООБЩЕНИЙ ПО СОСТОЯНИЮ =====
# ============================================
@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'document'])
def handle_all_messages(message):
    user_id = str(message.from_user.id)
    state = get_state(user_id)
    
    # Если нет состояния - показываем меню
    if not state:
        bot.send_message(
            message.chat.id,
            "❗ Используйте кнопки меню или команду /start",
            reply_markup=get_main_menu()
        )
        return
    
    # Обработка отмены
    if message.text and is_cancel(message.text):
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "❌ Действие отменено.",
            reply_markup=get_main_menu()
        )
        return
    
    # ===== ОБРАБОТКА СОСТОЯНИЙ =====
    
    # ----- АНКЕТА ХЕЛПЕРА -----
    if state == 'helper_name':
        set_data(user_id, 'name', message.text)
        set_state(user_id, 'helper_age')
        bot.send_message(
            message.chat.id,
            "📅 Введите *возраст*:",
            parse_mode='Markdown'
        )
        return
    
    if state == 'helper_age':
        if not message.text.isdigit():
            bot.send_message(
                message.chat.id,
                "⛔ Введите возраст *цифрами*:",
                parse_mode='Markdown'
            )
            return
        set_data(user_id, 'age', message.text)
        set_state(user_id, 'helper_experience')
        bot.send_message(
            message.chat.id,
            "💬 Расскажите о *опыте*:",
            parse_mode='Markdown'
        )
        return
    
    if state == 'helper_experience':
        set_data(user_id, 'experience', message.text)
        set_state(user_id, 'helper_contact')
        bot.send_message(
            message.chat.id,
            "📱 Оставьте *контакт* для связи:",
            parse_mode='Markdown'
        )
        return
    
    if state == 'helper_contact':
        set_data(user_id, 'contact', message.text)
        data = get_data(user_id)
        text = (
            f"👤 *Имя:* {data.get('name')}\n"
            f"📅 *Возраст:* {data.get('age')}\n"
            f"💬 *Опыт:* {data.get('experience')}\n"
            f"📱 *Контакт:* {data.get('contact')}"
        )
        user_name = message.from_user.username or message.from_user.first_name
        send_to_channel("📋 ЗАЯВКА НА ХЕЛПЕРА", text, message.from_user.id, user_name)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ *Заявка отправлена!*\n\nМы свяжемся с вами в ближайшее время.",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return
    
    # ----- ТЕХПОДДЕРЖКА -----
    if state == 'support_problem':
        if message.text:
            text = message.text
        elif message.photo:
            text = "🖼 Скриншот приложен"
        elif message.document:
            text = "📎 Файл приложен"
        else:
            text = "Сообщение без текста"
        
        user_name = message.from_user.username or message.from_user.first_name
        send_to_channel("🔧 ОБРАЩЕНИЕ В ТЕХПОДДЕРЖКУ", f"📝 {text}", message.from_user.id, user_name)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ *Обращение отправлено!*\n\nТехподдержка свяжется с вами.",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return
    
    # ----- ЖАЛОБА -----
    if state == 'complain_against':
        set_data(user_id, 'against', message.text)
        set_state(user_id, 'complain_reason')
        bot.send_message(
            message.chat.id,
            "📝 Опишите *причину* жалобы:",
            parse_mode='Markdown'
        )
        return
    
    if state == 'complain_reason':
        set_data(user_id, 'reason', message.text)
        set_state(user_id, 'complain_evidence')
        bot.send_message(
            message.chat.id,
            "📎 Приложите *доказательства* (скриншот) или напишите 'нет':",
            parse_mode='Markdown'
        )
        return
    
    if state == 'complain_evidence':
        if message.text:
            evidence = message.text
        elif message.photo:
            evidence = "🖼 Скриншот приложен"
        elif message.document:
            evidence = "📎 Файл приложен"
        else:
            evidence = "Без доказательств"
        
        set_data(user_id, 'evidence', evidence)
        data = get_data(user_id)
        text = (
            f"👤 *Жалоба на:* {data.get('against')}\n"
            f"📝 *Причина:* {data.get('reason')}\n"
            f"📎 *Доказательства:* {data.get('evidence')}"
        )
        user_name = message.from_user.username or message.from_user.first_name
        send_to_channel("⚠️ НОВАЯ ЖАЛОБА", text, message.from_user.id, user_name)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ *Жалоба отправлена!*\n\nАдминистрация рассмотрит её.",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return
    
    # Если состояние не распознано
    clear_state(user_id)
    bot.send_message(
        message.chat.id,
        "❗ Что-то пошло не так. Начните заново с /start",
        reply_markup=get_main_menu()
    )

# ===== ЗАПУСК =====
def run_bot():
    print("🤖 Запуск Telegram бота...")
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)

if __name__ == "__main__":
    print("🚀 Запуск VIBE RUSSIA Bot...")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Запуск Flask сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)
