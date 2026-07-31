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
    """Красивое меню с эмодзи"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🙋‍♂️ Стать Хелпером")
    btn2 = types.KeyboardButton("🛠 Техподдержка")
    btn3 = types.KeyboardButton("⚠️ Подать жалобу")
    btn4 = types.KeyboardButton("ℹ️ О боте")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

def get_cancel_menu():
    """Кнопка отмены"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))
    return markup

def is_cancel(text):
    """Проверяет, является ли текст командой отмены"""
    return text and (text.lower() in ["❌ отмена", "отмена", "/cancel"])

# ===== КОМАНДЫ =====
@bot.message_handler(commands=['start'])
def start(message):
    """Приветственное сообщение с красивым оформлением"""
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
        "🙋‍♂️ *Стать Хелпером* — заполни анкету для вступления в команду\n"
        "🛠 *Техподдержка* — сообщи о проблеме или ошибке\n"
        "⚠️ *Подать жалобу* — сообщи о нарушении правил\n\n"
        "❌ *Отмена* — отменить текущее действие\n\n"
        "Все заявки отправляются администрации проекта."
    )
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

# ===== ОБРАБОТКА ТЕКСТОВЫХ КОМАНД =====
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower() in ["хелпер", "стать хелпером", "helper"])
def helper_text_command(message):
    start_helper(message)

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower() in ["техподдержка", "поддержка", "support", "помощь"])
def support_text_command(message):
    start_support(message)

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower() in ["жалоба", "подать жалобу", "complain"])
def complain_text_command(message):
    start_complain(message)

# ===== КНОПКИ МЕНЮ =====
@bot.message_handler(func=lambda msg: msg.text == "🙋‍♂️ Стать Хелпером")
def start_helper(message):
    bot.set_state(message.from_user.id, UserStates.helper_name, message.chat.id)
    bot.send_message(
        message.chat.id,
        "📝 *Заявка на Хелпера*\n\n"
        "Пожалуйста, введите ваши *Имя и Фамилию*:",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "🛠 Техподдержка")
def start_support(message):
    bot.set_state(message.from_user.id, UserStates.support_problem, message.chat.id)
    bot.send_message(
        message.chat.id,
        "🔧 *Обращение в техподдержку*\n\n"
        "Опишите вашу проблему как можно подробнее.\n"
        "Можете приложить скриншот или файл.",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "⚠️ Подать жалобу")
def start_complain(message):
    bot.set_state(message.from_user.id, UserStates.complain_against, message.chat.id)
    bot.send_message(
        message.chat.id,
        "⚠️ *Подача жалобы*\n\n"
        "Укажите ник или ID человека, на которого хотите пожаловаться:",
        parse_mode='Markdown',
        reply_markup=get_cancel_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ О боте")
def about(message):
    about_text = (
        "🤖 *VIBE RUSSIA Bot*\n\n"
        "Версия: 2.0\n"
        "Разработан для проекта VIBE RUSSIA\n\n"
        "📌 *Назначение:*\n"
        "• Прием заявок на Хелперов\n"
        "• Обработка обращений в техподдержку\n"
        "• Прием жалоб\n\n"
        "💡 *Все заявки автоматически отправляются администрации.*"
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

# ===== ОБРАБОТКА АНКЕТЫ ХЕЛПЕРА =====
@bot.message_handler(state=UserStates.helper_name)
def process_helper_name(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📅 Введите ваш *возраст*:", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.helper_age, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text

@bot.message_handler(state=UserStates.helper_age)
def process_helper_age(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "⛔ Пожалуйста, введите возраст *цифрами*:", parse_mode='Markdown')
        return
    
    bot.send_message(message.chat.id, "💬 Расскажите о вашем *опыте* или почему хотите стать Хелпером:", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.helper_experience, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['age'] = message.text

@bot.message_handler(state=UserStates.helper_experience)
def process_helper_experience(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📱 Оставьте *контакт* для связи (Telegram, Discord или номер телефона):", parse_mode='Markdown')
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
        "✅ *Заявка успешно отправлена!*\n\n"
        "Мы свяжемся с вами в ближайшее время.\n"
        "Спасибо за интерес к проекту! 🙌",
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

# ===== ОБРАБОТКА ТЕХПОДДЕРЖКИ =====
@bot.message_handler(state=UserStates.support_problem, content_types=['text', 'photo', 'document'])
def process_support(message):
    if message.text and is_cancel(message.text):
        cancel_action(message)
        return
    
    if message.text:
        text = f"📝 {message.text}"
    elif message.photo:
        text = "🖼 Скриншот приложен"
    elif message.document:
        text = "📎 Файл приложен"
    else:
        text = "Сообщение без текста"
    
    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("🔧 ОБРАЩЕНИЕ В ТЕХПОДДЕРЖКУ", text, message.from_user.id, user_name)
    bot.delete_state(message.from_user.id, message.chat.id)
    
    bot.send_message(
        message.chat.id,
        "✅ *Обращение отправлено!*\n\n"
        "Техподдержка свяжется с вами в ближайшее время.",
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

# ===== ОБРАБОТКА ЖАЛОБЫ =====
@bot.message_handler(state=UserStates.complain_against)
def process_complain_against(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📝 Опишите *причину жалобы* подробно:", parse_mode='Markdown')
    bot.set_state(message.from_user.id, UserStates.complain_reason, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['against'] = message.text

@bot.message_handler(state=UserStates.complain_reason)
def process_complain_reason(message):
    if is_cancel(message.text):
        cancel_action(message)
        return
    
    bot.send_message(message.chat.id, "📎 Приложите *доказательства* (скриншот, ссылка) или напишите 'нет':", parse_mode='Markdown')
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
        "✅ *Жалоба отправлена!*\n\n"
        "Администрация рассмотрит её в ближайшее время.",
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

# ===== ОБРАБОТКА ВСЕХ ОСТАЛЬНЫХ СООБЩЕНИЙ =====
@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    # Проверяем, есть ли активное состояние
    state = bot.get_state(message.from_user.id, message.chat.id)
    if state:
        # Если есть состояние, но пользователь ввел что-то другое
        bot.send_message(
            message.chat.id,
            "❗ Пожалуйста, следуйте инструкциям или нажмите ❌ Отмена",
            reply_markup=get_cancel_menu()
        )
    else:
        # Если нет состояния, показываем меню
        bot.send_message(
            message.chat.id,
            "❗ Используйте кнопки меню или команду /start",
            reply_markup=get_main_menu()
        )

# ===== ЗАПУСК БОТА =====
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
