import telebot
from telebot import types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import os
import time
import logging
from datetime import datetime
from flask import Flask
import threading

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
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(BOT_TOKEN, state_storage=state_storage)

# ===== СОСТОЯНИЯ =====
class UserStates(StatesGroup):
    helper_name = State()
    helper_age = State()
    helper_experience = State()
    helper_contact = State()
    support_problem = State()
    complain_against = State()
    complain_reason = State()
    complain_evidence = State()

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

def is_cancel(text):
    return text and text in ["❌ Отмена", "Отмена", "/cancel"]

# ============================================
# ===== КОМАНДЫ =====
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
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
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(
        message.chat.id,
        "❌ Действие отменено.",
        reply_markup=get_main_menu()
    )

# ============================================
# ===== КНОПКИ МЕНЮ (УСТАНАВЛИВАЮТ СОСТОЯНИЕ) =====
# ============================================
@bot.message_handler(func=lambda msg: msg.text == "🙋‍♂️ Стать Хелпером")
def start_helper(message):
    bot.set_state(message.from_user.id, UserStates.helper_name, message.chat.id)
    bot.send_message(
        message.chat.id,
        "📝 *Заявка на Хелпера*\n\nВведите ваши *Имя и Фамилию*:",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "🛠 Техподдержка")
def start_support(message):
    bot.set_state(message.from_user.id, UserStates.support_problem, message.chat.id)
    bot.send_message(
        message.chat.id,
        "🔧 *Обращение в техподдержку*\n\nОпишите проблему. Можно приложить скриншот.",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "⚠️ Подать жалобу")
def start_complain(message):
    bot.set_state(message.from_user.id, UserStates.complain_against, message.chat.id)
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
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(
        message.chat.id,
        "❌ Действие отменено.",
        reply_markup=get_main_menu()
    )

# ============================================
# ===== ОБРАБОТКА СОСТОЯНИЙ =====
# ============================================

# ----- АНКЕТА ХЕЛПЕРА -----
@bot.message_handler(state=UserStates.helper_name)
def process_helper_name(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📅 Введите *возраст*:", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.helper_age, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text

@bot.message_handler(state=UserStates.helper_age)
def process_helper_age(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "⛔ Введите возраст *цифрами*:", parse_mode='Markdown')
        return
    
    bot.send_message(message.chat.id, "💬 Расскажите о *опыте*:", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.helper_experience, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['age'] = message.text

@bot.message_handler(state=UserStates.helper_experience)
def process_helper_experience(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📱 Оставьте *контакт* для связи:", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.helper_contact, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['experience'] = message.text

@bot.message_handler(state=UserStates.helper_contact)
def process_helper_contact(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['contact'] = message.text
        text = (
            f"👤 *Имя:* {data.get('name')}\n"
            f"📅 *Возраст:* {data.get('age')}\n"
            f"💬 *Опыт:* {data.get('experience')}\n"
            f"📱 *Контакт:* {data.get('contact')}"
        )
    
    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("📋 ЗАЯВКА НА ХЕЛПЕРА", text, message.from_user.id, user_name)
    bot.delete_state(message.from_user.id, message.chat.id)
    
    bot.send_message(
        message.chat.id,
        "✅ *Заявка отправлена!*\n\nМы свяжемся с вами в ближайшее время.",
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

# ----- ТЕХПОДДЕРЖКА -----
@bot.message_handler(state=UserStates.support_problem, content_types=['text', 'photo', 'document'])
def process_support(message):
    if message.text and is_cancel(message.text):
        cancel_action(message)
        return
    
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
    bot.delete_state(message.from_user.id, message.chat.id)
    
    bot.send_message(
        message.chat.id,
        "✅ *Обращение отправлено!*\n\nТехподдержка свяжется с вами.",
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

# ----- ЖАЛОБА -----
@bot.message_handler(state=UserStates.complain_against)
def process_complain_against(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📝 Опишите *причину* жалобы:", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.complain_reason, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['against'] = message.text

@bot.message_handler(state=UserStates.complain_reason)
def process_complain_reason(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📎 Приложите *доказательства* (скриншот) или напишите 'нет':", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.complain_evidence, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['reason'] = message.text

@bot.message_handler(state=UserStates.complain_evidence, content_types=['text', 'photo', 'document'])
def process_complain_evidence(message):
    if message.text and is_cancel(message.text):
        cancel_action(message)
        return
    
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        if message.text:
            evidence = message.text
        elif message.photo:
            evidence = "🖼 Скриншот приложен"
        elif message.document:
            evidence = "📎 Файл приложен"
        else:
            evidence = "Без доказательств"
        
        data['evidence'] = evidence
        text = (
            f"👤 *Жалоба на:* {data.get('against')}\n"
            f"📝 *Причина:* {data.get('reason')}\n"
            f"📎 *Доказательства:* {evidence}"
        )
    
    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("⚠️ НОВАЯ ЖАЛОБА", text, message.from_user.id, user_name)
    bot.delete_state(message.from_user.id, message.chat.id)
    
    bot.send_message(
        message.chat.id,
        "✅ *Жалоба отправлена!*\n\nАдминистрация рассмотрит её.",
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

# ============================================
# ===== ВСЕ ОСТАЛЬНЫЕ СООБЩЕНИЯ =====
# ============================================
@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    bot.send_message(
        message.chat.id,
        "❗ Используйте кнопки меню или команду /start",
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
