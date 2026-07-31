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

# ⚠️ ВСТАВЬТЕ СВОЙ ID СЮДА!
ADMIN_IDS = [8718572838]  # Ваш ID из @userinfobot

# Версия бота (меняется через админ-панель)
BOT_VERSION = "2.0.0"

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ Ошибка: BOT_TOKEN или CHANNEL_ID не заданы!")
    exit(1)

# ===== FLASK =====
app = Flask(__name__)

@app.route('/')
def index():
    return "🤖 VIBE RUSSIA Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

# ===== БОТ =====
bot = telebot.TeleBot(BOT_TOKEN)

# ===== ХРАНИЛИЩЕ =====
user_states = {}
user_data = {}
applications = {}
users = {}  # {user_id: {'first_seen': ..., 'last_seen': ...}}

# ===== ФУНКЦИИ =====
def get_state(user_id):
    return user_states.get(str(user_id))

def set_state(user_id, state):
    user_states[str(user_id)] = state

def clear_state(user_id):
    if str(user_id) in user_states:
        del user_states[str(user_id)]
    if str(user_id) in user_data:
        del user_data[str(user_id)]

def get_data(user_id):
    return user_data.get(str(user_id), {})

def set_data(user_id, key, value):
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    user_data[str(user_id)][key] = value

def is_cancel(text):
    return text and text in ["❌ Отмена", "Отмена", "/cancel"]

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

def save_user(user_id, username=None):
    """Сохраняет информацию о пользователе"""
    user_id = str(user_id)
    now = datetime.now().isoformat()
    if user_id not in users:
        users[user_id] = {
            'first_seen': now,
            'username': username,
            'last_seen': now
        }
    else:
        users[user_id]['last_seen'] = now
        if username:
            users[user_id]['username'] = username

def send_application_to_channel(app_type, text, user_id, user_name=None):
    try:
        app_id = int(time.time())
        applications[app_id] = {
            'user_id': user_id,
            'type': app_type,
            'data': text,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        header = f"📩 НОВАЯ ЗАЯВКА: {app_type}\n"
        header += f"🆔 Заявка: #{app_id}\n"
        header += f"👤 От: @{user_name or user_id}\n"
        header += f"🆔 ID: {user_id}\n"
        header += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_approve = types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{app_id}")
        btn_reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app_id}")
        btn_take = types.InlineKeyboardButton("📌 Взять в работу", callback_data=f"take_{app_id}")
        btn_close = types.InlineKeyboardButton("✅ Закрыть", callback_data=f"close_{app_id}")
        markup.add(btn_approve, btn_reject, btn_take, btn_close)
        
        bot.send_message(CHANNEL_ID, header + text, reply_markup=markup)
        return app_id
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def notify_all_users(message_text):
    """Отправляет уведомление всем пользователям"""
    count = 0
    for user_id in users.keys():
        try:
            bot.send_message(
                int(user_id),
                f"📢 *Уведомление от VIBE RUSSIA*\n\n{message_text}",
                parse_mode='Markdown'
            )
            count += 1
            time.sleep(0.1)  # Чтобы не заблокировали
        except:
            pass
    return count

# ============================================
# ===== ОБРАБОТКА КНОПОК =====
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    user_id = call.from_user.id
    
    if not call.data.startswith('status'):
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ У вас нет прав!", show_alert=True)
            return
    
    # ===== АДМИН-ПАНЕЛЬ =====
    if call.data == 'admin_all':
        if not applications:
            bot.edit_message_text("📭 *Нет заявок*", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            bot.answer_callback_query(call.id, "📭 Нет заявок")
            return
        
        text = "📋 *ВСЕ ЗАЯВКИ*\n\n"
        for app_id, app in list(applications.items())[-10:]:
            status = app.get('status', 'pending')
            emoji = {'pending': '⏳', 'approved': '✅', 'rejected': '❌', 'in_progress': '📌', 'closed': '✅'}.get(status, '❓')
            text += f"{emoji} #{app_id} | {app.get('type', '?')}\n👤 {app.get('user_id')}\n📌 {status.upper()}\n\n"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.answer_callback_query(call.id, "✅ Показаны все заявки")
        return
    
    if call.data == 'admin_pending':
        pending = {k: v for k, v in applications.items() if v.get('status') == 'pending'}
        if not pending:
            bot.edit_message_text("✅ *Нет заявок в ожидании*", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            bot.answer_callback_query(call.id, "✅ Нет заявок")
            return
        
        text = "⏳ *ЗАЯВКИ В ОЖИДАНИИ*\n\n"
        for app_id, app in pending.items():
            text += f"#{app_id} | {app.get('type', '?')}\n👤 {app.get('user_id')}\n\n"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.answer_callback_query(call.id, "✅ Показаны заявки в ожидании")
        return
    
    if call.data == 'admin_stats':
        total = len(applications)
        pending = len([a for a in applications.values() if a.get('status') == 'pending'])
        approved = len([a for a in applications.values() if a.get('status') == 'approved'])
        rejected = len([a for a in applications.values() if a.get('status') == 'rejected'])
        in_progress = len([a for a in applications.values() if a.get('status') == 'in_progress'])
        
        text = (
            "📊 *СТАТИСТИКА*\n\n"
            f"📋 Всего заявок: {total}\n"
            f"⏳ В ожидании: {pending}\n"
            f"📌 В работе: {in_progress}\n"
            f"✅ Одобрено: {approved}\n"
            f"❌ Отклонено: {rejected}\n"
            f"👥 Всего пользователей: {len(users)}\n\n"
            f"🤖 Версия бота: v{BOT_VERSION}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.answer_callback_query(call.id, "✅ Статистика")
        return
    
    if call.data == 'admin_clear':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Да, удалить всё", callback_data="admin_clear_yes"),
            types.InlineKeyboardButton("❌ Нет, отмена", callback_data="admin_clear_no")
        )
        bot.edit_message_text(
            "⚠️ *УДАЛИТЬ ВСЕ ЗАЯВКИ?*\n\nЭто действие нельзя отменить!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "⚠️ Подтвердите")
        return
    
    if call.data == 'admin_clear_yes':
        applications.clear()
        bot.edit_message_text("🗑 *Все заявки удалены*", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.answer_callback_query(call.id, "✅ Удалено")
        return
    
    if call.data == 'admin_clear_no':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📋 Все заявки", callback_data="admin_all"),
            types.InlineKeyboardButton("⏳ В ожидании", callback_data="admin_pending"),
            types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
            types.InlineKeyboardButton("🗑 Очистить все", callback_data="admin_clear")
        )
        bot.edit_message_text(
            "🔐 *Админ-панель*\n\nВыберите действие:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "✅ Отменено")
        return
    
    # ===== КНОПКИ УПРАВЛЕНИЯ ЗАЯВКАМИ =====
    if call.data.startswith('approve_') or call.data.startswith('reject_') or call.data.startswith('take_') or call.data.startswith('close_'):
        action, app_id = call.data.split('_')
        app_id = int(app_id)
        
        if app_id not in applications:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена!", show_alert=True)
            return
        
        app = applications[app_id]
        
        if action == 'approve':
            app['status'] = 'approved'
            status_text = "✅ ОДОБРЕНА"
            user_text = "✅ Ваша заявка ОДОБРЕНА! Поздравляем! 🎉"
        elif action == 'reject':
            app['status'] = 'rejected'
            status_text = "❌ ОТКЛОНЕНА"
            user_text = "❌ Заявка ОТКЛОНЕНА. Свяжитесь с администрацией."
        elif action == 'take':
            app['status'] = 'in_progress'
            status_text = "📌 В РАБОТЕ"
            user_text = "📌 Заявка ВЗЯТА В РАБОТУ! Скоро свяжемся."
        elif action == 'close':
            app['status'] = 'closed'
            status_text = "✅ ЗАКРЫТА"
            user_text = "✅ Заявка ЗАКРЫТА. Спасибо за обращение!"
        else:
            bot.answer_callback_query(call.id, "❌ Неизвестно")
            return
        
        try:
            old_text = call.message.text
            if '\n\n📌 СТАТУС:' in old_text:
                old_text = old_text.split('\n\n📌 СТАТУС:')[0]
            if '\n\n👤 Админ:' in old_text:
                old_text = old_text.split('\n\n👤 Админ:')[0]
            
            new_text = f"{old_text}\n\n📌 СТАТУС: {status_text}\n👤 Админ: @{call.from_user.username or call.from_user.first_name}"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton(f"📌 {status_text}", callback_data="status"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=new_text,
                reply_markup=markup
            )
            
            try:
                bot.send_message(app['user_id'], user_text)
            except:
                pass
            
            bot.answer_callback_query(call.id, f"✅ {status_text}")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:30]}")
        return
    
    if call.data == 'status':
        bot.answer_callback_query(call.id, "📌 Текущий статус заявки")
        return
    
    bot.answer_callback_query(call.id, "❓ Неизвестная команда")

# ============================================
# ===== КОМАНДЫ =====
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    clear_state(message.from_user.id)
    user_name = message.from_user.first_name
    username = message.from_user.username
    
    # Сохраняем пользователя
    save_user(message.from_user.id, username)
    
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
    
    if message.from_user.id in ADMIN_IDS:
        welcome_text += "\n\n🔐 *Админ-панель:* /admin\n📌 *Сменить версию:* /setversion"
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав администратора!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📋 Все заявки", callback_data="admin_all"),
        types.InlineKeyboardButton("⏳ В ожидании", callback_data="admin_pending"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("🗑 Очистить все", callback_data="admin_clear")
    )
    
    bot.send_message(
        message.chat.id,
        f"🔐 *Админ-панель*\n\n🤖 Версия: v{BOT_VERSION}\n👥 Пользователей: {len(users)}\n\nВыберите действие:",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['setversion'])
def set_version(message):
    """Команда для смены версии бота (только для админов)"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав администратора!")
        return
    
    global BOT_VERSION
    
    # Разбираем команду: /setversion 2.1.0
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(
            message,
            f"📌 *Текущая версия:* v{BOT_VERSION}\n\n"
            "📝 *Как изменить:*\n"
            "`/setversion 2.1.0`\n\n"
            "💡 *Пример:* `/setversion 3.0.0`",
            parse_mode='Markdown'
        )
        return
    
    new_version = args[1]
    old_version = BOT_VERSION
    BOT_VERSION = new_version
    
    # Отправляем уведомление всем пользователям
    notify_text = (
        f"🔄 *Обновление бота!*\n\n"
        f"Бот VIBE RUSSIA обновлён до версии *v{new_version}*\n\n"
        f"📌 *Что нового:*\n"
        f"• Улучшена стабильность\n"
        f"• Исправлены мелкие баги\n"
        f"• Добавлены новые функции\n\n"
        f"Спасибо, что вы с нами! ❤️"
    )
    
    count = notify_all_users(notify_text)
    
    bot.reply_to(
        message,
        f"✅ *Версия обновлена!*\n\n"
        f"📌 *Старая версия:* v{old_version}\n"
        f"📌 *Новая версия:* v{new_version}\n"
        f"👥 *Уведомлено пользователей:* {count}\n\n"
        f"Все пользователи получили уведомление! 🎉",
        parse_mode='Markdown'
    )

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
        f"📌 *Версия:* v{BOT_VERSION}\n"
        f"📅 *Дата сборки:* {datetime.now().strftime('%d.%m.%Y')}\n\n"
        "📋 *Назначение:*\n"
        "• Прием заявок на Хелперов\n"
        "• Обработка обращений в техподдержку\n"
        "• Прием жалоб\n\n"
        f"👥 *Всего пользователей:* {len(users)}\n\n"
        "💡 *Разработано для VIBE RUSSIA*\n"
        "❤️ Спасибо, что вы с нами!"
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
# ===== ОБРАБОТКА СООБЩЕНИЙ =====
# ============================================

@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'document'])
def handle_all_messages(message):
    user_id = str(message.from_user.id)
    state = get_state(user_id)
    
    # Сохраняем пользователя
    save_user(message.from_user.id, message.from_user.username)
    
    if not state:
        if message.text in ["🙋‍♂️ Стать Хелпером", "🛠 Техподдержка", "⚠️ Подать жалобу", "ℹ️ О боте", "❌ Отмена"]:
            return
        
        # Проверяем команды админа
        if message.text and message.text.startswith('/setversion'):
            return
        
        bot.send_message(
            message.chat.id,
            "❗ Используйте кнопки меню или команду /start",
            reply_markup=get_main_menu()
        )
        return
    
    if is_cancel(message.text):
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "❌ Действие отменено.",
            reply_markup=get_main_menu()
        )
        return
    
    # ===== АНКЕТА ХЕЛПЕРА =====
    if state == 'helper_name':
        set_data(user_id, 'name', message.text)
        set_state(user_id, 'helper_age')
        bot.send_message(message.chat.id, "📅 Введите *возраст*:", parse_mode='Markdown')
        return
    
    if state == 'helper_age':
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "⛔ Введите возраст *цифрами*:", parse_mode='Markdown')
            return
        set_data(user_id, 'age', message.text)
        set_state(user_id, 'helper_experience')
        bot.send_message(message.chat.id, "💬 Расскажите о *опыте*:", parse_mode='Markdown')
        return
    
    if state == 'helper_experience':
        set_data(user_id, 'experience', message.text)
        set_state(user_id, 'helper_contact')
        bot.send_message(message.chat.id, "📱 Оставьте *контакт* для связи:", parse_mode='Markdown')
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
        send_application_to_channel("📋 ЗАЯВКА НА ХЕЛПЕРА", text, message.from_user.id, user_name)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ *Заявка отправлена!*\n\nМы свяжемся с вами.",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return
    
    # ===== ТЕХПОДДЕРЖКА =====
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
        send_application_to_channel("🔧 ТЕХПОДДЕРЖКА", f"📝 {text}", message.from_user.id, user_name)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ *Обращение отправлено!*\n\nТехподдержка свяжется с вами.",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return
    
    # ===== ЖАЛОБА =====
    if state == 'complain_against':
        set_data(user_id, 'against', message.text)
        set_state(user_id, 'complain_reason')
        bot.send_message(message.chat.id, "📝 Опишите *причину* жалобы:", parse_mode='Markdown')
        return
    
    if state == 'complain_reason':
        set_data(user_id, 'reason', message.text)
        set_state(user_id, 'complain_evidence')
        bot.send_message(message.chat.id, "📎 Приложите *доказательства* или напишите 'нет':", parse_mode='Markdown')
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
        send_application_to_channel("⚠️ ЖАЛОБА", text, message.from_user.id, user_name)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ *Жалоба отправлена!*\n\nАдминистрация рассмотрит её.",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return
    
    clear_state(user_id)
    bot.send_message(
        message.chat.id,
        "❗ Что-то пошло не так. Начните заново с /start",
        reply_markup=get_main_menu()
    )

# ============================================
# ===== ЗАПУСК =====
# ============================================

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
