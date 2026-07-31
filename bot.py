import telebot
from telebot import types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import os
import logging
from datetime import datetime
from flask import Flask, request

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ Ошибка: BOT_TOKEN или CHANNEL_ID не заданы!")
    exit(1)

# ===== FLASK APP =====
app = Flask(__name__)

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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🙋 Подать заявку на Хелпера")
    btn2 = types.KeyboardButton("🛠 Обратиться в техподдержку")
    btn3 = types.KeyboardButton("⚠️ Подать жалобу")
    markup.add(btn1, btn2, btn3)
    return markup

# ===== КОМАНДЫ =====
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в VIBE RUSSIA!\nВыберите нужный пункт меню:",
        reply_markup=get_main_menu()
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📖 Помощь по боту VIBE RUSSIA\n\n"
        "🙋 Подать заявку на Хелпера\n"
        "🛠 Обратиться в техподдержку\n"
        "⚠️ Подать жалобу",
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda msg: msg.text == "🙋 Подать заявку на Хелпера")
def start_helper(message):
    bot.set_state(message.from_user.id, UserStates.helper_name, message.chat.id)
    bot.send_message(
        message.chat.id,
        "📝 Введите ваше Имя и Фамилию:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "🛠 Обратиться в техподдержку")
def start_support(message):
    bot.set_state(message.from_user.id, UserStates.support_problem, message.chat.id)
    bot.send_message(
        message.chat.id,
        "🔧 Опишите вашу проблему:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "⚠️ Подать жалобу")
def start_complain(message):
    bot.set_state(message.from_user.id, UserStates.complain_against, message.chat.id)
    bot.send_message(
        message.chat.id,
        "⚠️ Укажите ник или ID человека:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(state=UserStates.helper_name)
def process_helper_name(message):
    if message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Отменено.", reply_markup=get_main_menu())
        return
    bot.send_message(message.chat.id, "📅 Введите возраст:")
    bot.set_state(message.from_user.id, UserStates.helper_age, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text

@bot.message_handler(state=UserStates.helper_age)
def process_helper_age(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "⛔ Введите цифры!")
        return
    bot.send_message(message.chat.id, "💬 Расскажите о вашем опыте:")
    bot.set_state(message.from_user.id, UserStates.helper_experience, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['age'] = message.text

@bot.message_handler(state=UserStates.helper_experience)
def process_helper_experience(message):
    bot.send_message(message.chat.id, "📱 Оставьте контакт для связи:")
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
    bot.send_message(message.chat.id, "✅ Отправлено!", reply_markup=get_main_menu())

@bot.message_handler(state=UserStates.support_problem, content_types=['text', 'photo', 'document'])
def process_support(message):
    if message.text and message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Отменено.", reply_markup=get_main_menu())
        return
    text = message.text if message.text else "Файл/скриншот"
    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("ОБРАЩЕНИЕ В ТЕХПОДДЕРЖКУ", f"📝 {text}", message.from_user.id, user_name)
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(message.chat.id, "✅ Отправлено!", reply_markup=get_main_menu())

@bot.message_handler(state=UserStates.complain_against)
def process_complain_against(message):
    if message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Отменено.", reply_markup=get_main_menu())
        return
    bot.send_message(message.chat.id, "📝 Опишите причину:")
    bot.set_state(message.from_user.id, UserStates.complain_reason, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['against'] = message.text

@bot.message_handler(state=UserStates.complain_reason)
def process_complain_reason(message):
    bot.send_message(message.chat.id, "📎 Приложите доказательства (или напишите 'нет'):")
    bot.set_state(message.from_user.id, UserStates.complain_evidence, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['reason'] = message.text

@bot.message_handler(state=UserStates.complain_evidence, content_types=['text', 'photo', 'document'])
def process_complain_evidence(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        evidence = message.text if message.text else "Скриншот/файл"
        data['evidence'] = evidence
        text = (
            f"👤 Жалоба на: {data.get('against')}\n"
            f"📝 Причина: {data.get('reason')}\n"
            f"📎 Доказательства: {evidence}"
        )
    user_name = message.from_user.username or message.from_user.first_name
    send_to_channel("НОВАЯ ЖАЛОБА", text, message.from_user.id, user_name)
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(message.chat.id, "✅ Отправлено!", reply_markup=get_main_menu())

@bot.message_handler(commands=['cancel'])
def cancel(message):
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(message.chat.id, "❌ Отменено.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    bot.send_message(
        message.chat.id,
        "❗ Используйте кнопки меню.",
        reply_markup=get_main_menu()
    )

# ===== WEBHOOK =====
@app.route('/', methods=['GET'])
def index():
    return "🤖 VIBE RUSSIA Bot is running!", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# ===== НАСТРОЙКА ВЕБХУКА ПРИ ЗАПУСКЕ =====
def setup_webhook():
    """Устанавливает вебхук при запуске"""
    webhook_url = f"https://mybot-qeun.onrender.com/{BOT_TOKEN}"
    
    # Удаляем старый вебхук
    bot.remove_webhook()
    
    # Устанавливаем новый
    result = bot.set_webhook(url=webhook_url)
    
    if result:
        print(f"✅ Webhook успешно установлен: {webhook_url}")
    else:
        print(f"❌ Ошибка установки webhook: {webhook_url}")
    
    return result

# ===== ГЛАВНЫЙ ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Запуск VIBE RUSSIA Bot...")
    
    # Настраиваем вебхук
    setup_webhook()
    
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Запуск Flask сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)
