import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from database import init_db, get_user, register_user, update_bonus, get_stats, is_task_done, mark_task_done, add_balance

# ==========================================
# НАСТРОЙКИ
# ==========================================
TOKEN = os.getenv("8428594117:AAG8D4JIswkUVXxYgjiB3KFvPu4geemSbGs")
ADMIN_ID = int(os.getenv("8915047087"))

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
# ЗАДАНИЯ (Настрой под свои каналы/чаты)
# ==========================================
TASKS = [
    {
        "name": "Подпишись на канал CoinFlow News",
        "link": "https://t.me/CoinFlowNews",
        "reward": 500,
        "id": "task_channel"
    },
    {
        "name": "Вступи в чат общения",
        "link": "https://t.me/PrsAdvertisementMy",
        "reward": 300,
        "id": "task_chat"
    }
]

# ==========================================
# ФУНКЦИИ БОТА
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = get_user(user.id)
    last_bonus = user_data[4]
    
    if last_bonus != today:
        update_bonus(user.id, today)
        text = f"🎉 Вам начислен бонус 2500 COINS!\n💰 Баланс: {get_user(user.id)[3]} COINS"
    else:
        text = f"🏰 Добро пожаловать в CoinFlow!\n💰 Твой баланс: {get_user(user.id)[3]} COINS"
    
    await update.message.reply_text(text, reply_markup=main_keyboard)

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
    user_id = update.effective_user.id
    keyboard = []
    
    for task in TASKS:
        done = is_task_done(user_id, task["id"])
        if done:
            status = "✅ (Выполнено)"
        else:
            status = f"🔹 Получить {task['reward']} COINS"
        
        keyboard.append([InlineKeyboardButton(
            f"{task['name']} - {status}",
            callback_data=f"do_task_{task['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤑 Выбери задание:",
        reply_markup=reply_markup
    )

async def task_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_to_menu":
        await start(update, context)
        return
    
    if data.startswith("do_task_"):
        task_id = data.replace("do_task_", "")
        user_id = update.effective_user.id
        
        if is_task_done(user_id, task_id):
            await query.edit_message_text("✅ Ты уже выполнил это задание!")
            return
        
        task = next((t for t in TASKS if t["id"] == task_id), None)
        if not task:
            await query.edit_message_text("❌ Задание не найдено!")
            return
        
        await query.edit_message_text(
            f"🔗 Перейди по ссылке:\n{task['link']}\n\n"
            f"После выполнения нажми кнопку ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я выполнил!", callback_data=f"done_{task_id}")]
            ])
        )
    
    if data.startswith("done_"):
        task_id = data.replace("done_", "")
        user_id = update.effective_user.id
        
        if is_task_done(user_id, task_id):
            await query.edit_message_text("✅ Ты уже получил награду!")
            return
        
        task = next((t for t in TASKS if t["id"] == task_id), None)
        if not task:
            await query.edit_message_text("❌ Ошибка!")
            return
        
        add_balance(user_id, task["reward"])
        mark_task_done(user_id, task_id)
        
        await query.edit_message_text(
            f"🎉 Поздравляем! Ты получил {task['reward']} COINS!\n"
            f"💰 Новый баланс: {get_user(user_id)[3]} COINS"
        )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет доступа к админке!")
        return
    
    total_users, total_coins = get_stats()
    
    await update.message.reply_text(
        f"👑 Админ-панель\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Всего COINS в системе: {total_coins}\n"
        f"Ваш ID: {update.effective_user.id}",
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
        await update.message.reply_text("⏳ Эта функция находится в разработке! Скоро она заработает.")

# ==========================================
# ЗАПУСК БОТА И ВЕБ-СЕРВЕРА
# ==========================================
import aiohttp
from aiohttp import web

async def health_check(request):
    return web.Response(text="OK")

async def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(task_button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 CoinFlow запущен! Всё готово к работе.")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    port = int(os.environ.get('PORT', 8080))
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Веб-сервер запущен на порту {port}")

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
