import logging
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Импортируем нашу базу данных
from database import init_db, get_user, register_user, update_bonus, get_stats

# ==========================================
# НАСТРОЙКИ
# ==========================================
TOKEN = "ВАШ_ТОКЕН_БОТА"  # <--- ВСТАВЬТЕ СВОИ ДАННЫЕ
ADMIN_ID = 123456789      # <--- ВСТАВЬТЕ СВОЙ ID (Ваш айдишник)

# Инициализируем базу при запуске
init_db()

# ==========================================
# КНОПКИ (КЛАВИАТУРА)
# ==========================================
main_keyboard = ReplyKeyboardMarkup([
    ["🤑 Заработать", "📊 Мой кабинет"],
    ["📢 Рекламировать", "🧾 Чеки"],
    ["📎 Полезные ссылки", "🤖 Наши боты"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "👑 Админка"]
], resize_keyboard=True)

# ==========================================
# ФУНКЦИИ БОТА
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    
    # Проверяем бонус
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = get_user(user.id)
    last_bonus = user_data[4]
    
    if last_bonus != today:
        update_bonus(user.id, today)
        # Формируем сообщение о бонусе
        text = f"🎉 Вам начислен бонус 2500 COINS!\n💰 Баланс: {get_user(user.id)[3]} COINS"
    else:
        # Формируем обычное приветствие
        text = f"🏰 Добро пожаловать в PSR BOT!\n💰 Твой баланс: {get_user(user.id)[3]} COINS"
    
    # ОТПРАВЛЯЕМ СООБЩЕНИЕ И КНОПКИ ТОЛЬКО ОДИН РАЗ В КОНЦЕ
    await update.message.reply_text(text, reply_markup=main_keyboard)
    else:
        await update.message.reply_text(
            f"🏰 Добро пожаловать в PSR BOT!\n💰 Твой баланс: {get_user(user.id)[3]} COINS",
            reply_markup=main_keyboard
        )

async def my_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user:
        balance = user[3]
        await update.message.reply_text(
            f"📊 Мой кабинет\n"
            f"🆔 ID: {user[0]}\n"
            f"👤 Имя: {user[2]}\n"
            f"💰 Баланс: {balance} COINS"
        )

async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤑 Заработать COINS:\n\n"
        "1️⃣ Подпишись на канал @psrhelppiarbot (Получи 500 COINS)\n"
        "2️⃣ Вступи в чат (Получи 300 COINS)\n\n"
        "Скоро добавим задания!"
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет доступа к админке!")
        return
    
    total_users, total_coins = get_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    
    await update.message.reply_text(
        f"👑 Админ-панель\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Всего COINS в системе: {total_coins}\n"
        f"📅 Дата: {today}",
        reply_markup=admin_keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "📊 Мой кабинет":
        await my_cabinet(update, context)
    elif text == "🤑 Заработать":
        await earn(update, context)
    elif text == "👑 Админка" or text == "📊 Статистика":
        await admin_panel(update, context)
    else:
        await update.message.reply_text("Используй кнопки меню ниже 👇")

# ==========================================
# ЗАПУСК БОТА
# ==========================================

async def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 PSR BOT запущен!")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    try:
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
