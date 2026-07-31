import telebot
from telebot import types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import os
import time
from datetime import datetime
import logging
from flask import Flask, request
import threading

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not BOT_TOKEN or not CHANNEL_ID:
    logger.error("❌ Ошибка: BOT_TOKEN или CHANNEL_ID не заданы!")
    exit(1)

# ===== FLASK APP (для Web Service) =====
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 VIBE RUSSIA Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка вебхуков (если нужно)"""
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
    """Отправляет заявку в канал/чат"""
    try:
        header = f"📩 НОВАЯ ЗАЯВКА: {app_type}\n"
        header += f"👤 От: @{user_name or user_id}\n"
        header += f"🆔 ID: {user_id}\n"
        header += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        
        bot.send_message(CHANNEL_ID, header + text)
        logger.info(f"✅ Заявка отправлена в канал: {app_type}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в канал: {e}")
        return False

def get_main_menu():
    """Создает главное меню с кнопками"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🙋 Подать заявку на Хелпера")
    btn2 = types.KeyboardButton("🛠 Обратиться в техподдержку")
    btn3 = types.KeyboardButton("⚠️ Подать жалобу")
    markup.add(btn1, btn2, btn3)
    return markup

# ===== КОМАНДА /START =====
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в VIBE RUSSIA!\n"
        "Выберите нужный пункт меню:",
        reply_markup=get_main_menu()
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📖 **Помощь по боту VIBE RUSSIA**\n\n"
        "🙋 **Подать заявку на Хелпера** — заполните анкету\n"
        "🛠 **Обратиться в техподдержку** — опишите проблему\n"
        "⚠️ **Подать жалобу** — сообщите о нарушении\n\n"
        "Все заявки отправляются администрации.",
        reply_markup=get_main_menu()
    )

# ===== ОБРАБОТКА ГЛАВНЫХ КНОПОК =====
@bot.message_handler(func=lambda msg: msg.text == "🙋 Подать заявку на Хелпера")
def start_helper(message):
    bot.set_state(message.from_user.id, UserStates.helper_name, message.chat.id)
    bot.send_message(
        message.chat.id,
        "📝 Заполните анкету для вступления в команду Хелперов.\n"
        "Введите ваше Имя и Фамилию:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "🛠 Обратиться в техподдержку")
def start_support(message):
    bot.set_state(message.from_user.id, UserStates.support_problem, message.chat.id)
    bot.send_message(
        message.chat.id,
        "🔧 Опишите вашу проблему как можно подробнее:\n"
        "(Укажите, что именно случилось, и приложите скриншот, если нужно)",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "⚠️ Подать жалобу")
def start_complain(message):
    bot.set_state(message.from_user.id, UserStates.complain_against, message.chat.id)
    bot.send_message(
        message.chat.id,
        "⚠️ Подача жалобы.\n"
        "Укажите ник или ID человека, на которого жалуетесь:",
        reply_markup=types.ReplyKeyboardRemove()
    )

# ===== ОБРАБОТКА АНКЕТЫ ХЕЛПЕРА =====
@bot.message_handler(state=UserStates.helper_name)
def process_helper_name(message):
    if message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Заявка отменена.", reply_markup=get_main_menu())
        return

    bot.send_message(message.chat.id, "📅 Введите ваш возраст:")
    bot.set_state(message.from_user.id, UserStates.helper_age, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text

@bot.message_handler(state=UserStates.helper_age)
def process_helper_age(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "⛔ Введите возраст цифрами.")
        return

    bot.send_message(message.chat.id, "💬 Расскажите о вашем опыте работы (или почему вы хотите стать Хелпером):")
    bot.set_state(message.from_user.id, UserStates.helper_experience, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['age'] = message.text

@bot.message_handler(state=UserStates.helper_experience)
def process_helper_experience(message):
    bot.send_message(message.chat.id, "📱 Оставьте контакт для связи (Telegram, Discord или номер телефона):")
    bot.set_state(message.from_user.id, UserStates.helper_contact, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['experience'] = message.text

@bot.message_handler(state=UserStates.helper_contact)
def process_helper_contact(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['contact'] = message.text
        
        text = (
            f"👤 Имя: {data.get('name')}\n"
            f"📅 Возраст: {data.get('age')}\n"
            f"💬 Опыт: {data.get('experience')}\n"
            f"📱 Контакт: {data.get('contact')}"
        )

    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("ЗАЯВКА НА ХЕЛПЕРА", text, message.from_user.id, user_name)

    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(
        message.chat.id,
        "✅ Ваша заявка отправлена! Мы свяжемся с вами в ближайшее время.",
        reply_markup=get_main_menu()
    )

# ===== ОБРАБОТКА ТЕХПОДДЕРЖКИ =====
@bot.message_handler(state=UserStates.support_problem, content_types=['text', 'photo', 'document'])
def process_support(message):
    if message.text and message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Отменено.", reply_markup=get_main_menu())
        return

    text = ""
    
    if message.text:
        text = f"📝 Описание проблемы:\n{message.text}"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        caption = message.caption if message.caption else "Без описания"
        text = f"🖼 Скриншот: {file_url}\n\n📝 Описание: {caption}"
    elif message.document:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        caption = message.caption if message.caption else "Без описания"
        text = f"📎 Файл: {file_url}\n\n📝 Описание: {caption}"

    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("ОБРАЩЕНИЕ В ТЕХПОДДЕРЖКУ", text, message.from_user.id, user_name)

    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(
        message.chat.id,
        "✅ Ваше обращение отправлено! Техподдержка свяжется с вами.",
        reply_markup=get_main_menu()
    )

# ===== ОБРАБОТКА ЖАЛОБЫ =====
@bot.message_handler(state=UserStates.complain_against)
def process_complain_against(message):
    if message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Отменено.", reply_markup=get_main_menu())
        return

    bot.send_message(message.chat.id, "📝 Опишите причину жалобы (что произошло):")
    bot.set_state(message.from_user.id, UserStates.complain_reason, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['against'] = message.text

@bot.message_handler(state=UserStates.complain_reason)
def process_complain_reason(message):
    bot.send_message(message.chat.id, "📎 Приложите доказательства (скриншоты, ссылки) или напишите 'нет':")
    bot.set_state(message.from_user.id, UserStates.complain_evidence, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['reason'] = message.text

@bot.message_handler(state=UserStates.complain_evidence, content_types=['text', 'photo', 'document'])
def process_complain_evidence(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        evidence = ""

        if message.photo:
            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            evidence = f"🖼 Скриншот: https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        elif message.document:
            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            evidence = f"📎 Файл: https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        else:
            evidence = message.text

        data['evidence'] = evidence
        
        text = (
            f"👤 Жалоба на: {data.get('against')}\n"
            f"📝 Причина: {data.get('reason')}\n"
            f"📎 Доказательства: {evidence}"
        )

    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("НОВАЯ ЖАЛОБА", text, message.from_user.id, user_name)

    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(
        message.chat.id,
        "✅ Жалоба отправлена! Администрация рассмотрит её в ближайшее время.",
        reply_markup=get_main_menu()
    )

# ===== КОМАНДА /CANCEL =====
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
    bot.send_message(
        message.chat.id,
        "❗ Используйте кнопки меню или команды /start и /cancel.",
        reply_markup=get_main_menu()
    )

# ===== ЗАПУСК БОТА В ОТДЕЛЬНОМ ПОТОКЕ =====
def run_bot():
    """Запускает бота в отдельном потоке"""
    logger.info("🤖 Запуск Telegram бота...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"❌ Ошибка в polling: {e}")
            logger.info("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)

# ===== ГЛАВНЫЙ ЗАПУСК =====
if __name__ == "__main__":
    logger.info("🚀 Запуск VIBE RUSSIA Bot (Web Service)...")
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем Flask сервер (для Render Web Service)
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Запуск Flask сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)

