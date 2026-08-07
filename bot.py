import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from database import init_db, get_user, register_user, add_balance, get_balance, get_active_tasks, is_task_done, mark_task_done, get_stats

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

main_keyboard = ReplyKeyboardMarkup([
    ["🤑 Заработать", "📊 Мой кабинет"],
    ["📞 Поддержка", "🧾 Чеки"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "📢 Рассылка"],
    ["💰 Выдать монеты", "📝 Управление заданиями"],
    ["🔙 Выйти из админки"]
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = await get_user(user.id)
    last_bonus = user_data['last_bonus'] if user_data else None
    balance = await get_balance(user.id)
    
    if last_bonus != today:
        await add_balance(user.id, 2500)
        balance = await get_balance(user.id)
        await update.message.reply_text(f"🎉 Бонус! +2500 COINS\n💰 Баланс: {balance}")
    
    await update.message.reply_text(
        f"🏰 Добро пожаловать в CoinFlow!\n💰 Баланс: {balance} COINS",
        reply_markup=main_keyboard
    )

async def my_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = await get_balance(user_id)
    await update.message.reply_text(
        f"📊 Мой кабинет\n🆔 ID: {user_id}\n💰 Баланс: {balance} COINS"
    )

async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = await get_active_tasks()
    keyboard = []
    for task in tasks:
        done = await is_task_done(user_id, task['id'])
        status = "✅ Выполнено" if done else f"🔹 {task['reward']} COINS"
        keyboard.append([InlineKeyboardButton(
            f"{task['name']} - {status}",
            callback_data=f"do_{task['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    await update.message.reply_text(
        "🤑 Доступные задания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    if data == "back":
        await start(update, context)
        return
    if data.startswith("do_"):
        task_id = int(data.replace("do_", ""))
        if await is_task_done(user_id, task_id):
            await query.edit_message_text("✅ Уже выполнено!")
            return
        tasks = await get_active_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task:
            await query.edit_message_text("❌ Задание не найдено")
            return
        try:
            chat_member = await context.bot.get_chat_member(chat_id=task['channel_id'], user_id=user_id)
            if chat_member.status in ['member', 'administrator', 'creator']:
                await add_balance(user_id, task['reward'])
                await mark_task_done(user_id, task_id)
                await query.edit_message_text(f"✅ Задание выполнено! +{task['reward']} COINS")
            else:
                await query.edit_message_text(
                    f"❌ Ты не подписан на канал!\n👉 {task['link']}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Проверить ещё раз", callback_data=f"do_{task_id}")]
                    ])
                )
        except:
            await query.edit_message_text("❌ Ошибка проверки. Убедись, что канал публичный.")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 Поддержка:\nНапиши администратору в ЛС: @ArchibaldNn",
        reply_markup=ReplyKeyboardMarkup([["🔙 В меню"]], resize_keyboard=True)
    )
    context.user_data['support_mode'] = True

async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('support_mode') and update.effective_user.id != ADMIN_ID:
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 Сообщение в поддержку от {update.effective_user.id}:\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ Отправлено!")
        context.user_data['support_mode'] = False
        await start(update, context)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа")
        return
    total_users, total_coins = await get_stats()
    await update.message.reply_text(
        f"👑 Админка\n👥 Пользователей: {total_users}\n💰 COINS: {total_coins}",
        reply_markup=admin_keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 Мой кабинет":
        await my_cabinet(update, context)
    elif text == "🤑 Заработать":
        await earn(update, context)
    elif text == "📞 Поддержка":
        await support(update, context)
    elif context.user_data.get('support_mode'):
        await support_message(update, context)
    elif update.effective_user.id == ADMIN_ID and text == "👑 Админка":
        await admin_panel(update, context)
    else:
        await update.message.reply_text("⏳ В разработке")

async def main():
    await init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(task_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Бот запущен с PostgreSQL")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
