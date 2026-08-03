import os
import sqlite3
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "8428594117:AAHw06wgDdQ5rxc5SqR7gueh3l9ARVd_SCo"
ADMIN_ID = 8915047087

# Flask-заглушка
app_flask = Flask(__name__)

# ==========================================
# 2. БАЗА ДАННЫХ
# ==========================================
def init_db():
    conn = sqlite3.connect('krmp_users.db')
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        created_at TEXT
    )
    ''')
    conn.commit()
    conn.close()

init_db()

def register_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('krmp_users.db')
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
    finally:
        conn.close()

# ==========================================
# 3. МЕНЮ
# ==========================================
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📩 Связаться с Администрацией", callback_data="support")],
        [InlineKeyboardButton("ℹ️ О проекте BEST RUSSIA", callback_data="info")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# 4. ОБРАБОТЧИКИ
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)
    welcome_text = f"""
🎖 **Добро пожаловать в BEST RUSSIA (КРМП)!**

🆔 Ваш ID: `{user.id}`
👤 Никнейм: @{user.username or 'Отсутствует'}

Это официальный бот для связи с Администрацией.
Нажмите кнопку ниже, чтобы написать нам.
"""
    await update.message.reply_text(welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "support":
        await query.edit_message_text("📩 Напишите ваше сообщение. Администрация BEST RUSSIA прочитает его.")
    elif query.data == "info":
        await query.edit_message_text("ℹ️ BEST RUSSIA — развивающийся RP-проект. Все обращения рассматриваются вручную.", reply_markup=main_menu())

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    forward_msg = f"""
✉️ **НОВОЕ ОБРАЩЕНИЕ BEST RUSSIA**

🆔 ID: `{user.id}`
👤 Ник: @{user.username or 'Отсутствует'}

📝 **Текст:**
{text}
"""
    await context.bot.send_message(chat_id=ADMIN_ID, text=forward_msg, parse_mode="Markdown")
    await update.message.reply_text("✅ Ваше обращение отправлено Администрации!", reply_markup=main_menu())

# ==========================================
# 5. ЗАПУСК (С ПОТОКОМ ДЛЯ WEB SERVICE)
# ==========================================
if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin))

    print("🚀 Запуск бота BEST RUSSIA...")
    
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=application.run_polling, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask-заглушку для Render
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)
