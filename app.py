import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==========================================
# 1. НАСТРОЙКИ (ВСТАВЬТЕ СВОИ ДАННЫЕ)
# ==========================================
BOT_TOKEN = "8428594117:AAHw06wgDdQ5rxc5SqR7gueh3l9ARVd_SCo" 
ADMIN_ID = 8915047087  # Ваш Telegram ID

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
# 3. МЕНЮ И КЛАВИАТУРЫ
# ==========================================
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📩 Связаться с Администрацией", callback_data="support")],
        [InlineKeyboardButton("ℹ️ О проекте BEST RUSSIA", callback_data="info")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# 4. ОБРАБОТЧИКИ КОМАНД
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = f"""
🎖 **Добро пожаловать в BEST RUSSIA (КРМП)!**

🆔 Ваш ID: `{user.id}`
👤 Никнейм: @{user.username or 'Отсутствует'}
👤 Имя: {user.first_name}

Это официальный бот для связи с Администрацией проекта.
Если у вас есть вопросы, предложения или жалобы — нажмите кнопку ниже.
"""
    await update.message.reply_text(welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Нажмите 'Связаться с Администрацией', чтобы написать нам.", reply_markup=main_menu())

# ==========================================
# 5. ОБРАБОТЧИКИ НАЖАТИЙ КНОПОК
# ==========================================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "support":
        await query.edit_message_text(
            "📩 **Режим связи с Администрацией**\n\n"
            "Напишите ваше сообщение прямо сейчас. \n"
            "Администрация проекта BEST RUSSIA прочитает его в ближайшее время."
        )
    elif query.data == "info":
        await query.edit_message_text(
            "ℹ️ **О BEST RUSSIA**\n\n"
            "Мы — развивающийся RP-проект. \n"
            "Все ваши обращения рассматриваются вручную.",
            reply_markup=main_menu()
        )

# ==========================================
# 6. ОБРАБОТЧИК ТЕКСТА (Пересылка Вам)
# ==========================================
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    # Пересылаем сообщение администратору
    forward_msg = f"""
✉️ **НОВОЕ ОБРАЩЕНИЕ BEST RUSSIA**

🆔 **ID пользователя:** `{user.id}`
👤 **Никнейм:** @{user.username or 'Отсутствует'}
👤 **Имя:** {user.first_name} {user.last_name or ''}

📝 **Текст обращения:**
{text}

---
_Ответьте пользователю напрямую в ЛС._
"""
    await context.bot.send_message(chat_id=ADMIN_ID, text=forward_msg, parse_mode="Markdown")
    
    # Подтверждение пользователю
    await update.message.reply_text(
        "✅ Ваше обращение успешно отправлено Администрации BEST RUSSIA!\n\nОжидайте ответа в личные сообщения.",
        reply_markup=main_menu()
    )

# ==========================================
# 7. ЗАПУСК БОТА
# ==========================================
if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Ловим любой текст после нажатия кнопки
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin))
    
    print("🚀 Бот BEST RUSSIA запущен и готов к работе!")
    
    # Запускаем Polling (он не требует Webhook и работает стабильно)
    application.run_polling()
