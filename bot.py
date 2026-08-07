import os
import asyncio
import asyncpg
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler, ContextTypes

from database import init_db, get_user, register_user, add_balance, get_balance, get_active_tasks, is_task_done, mark_task_done, get_stats

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

main_keyboard = ReplyKeyboardMarkup([
    ["🤑 Заработать", "📊 Мой кабинет"],
    ["📞 Поддержка", "💳 Пополнить"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "📢 Рассылка"],
    ["💰 Выдать монеты", "📝 Управление заданиями"],
    ["🔙 Выйти из админки"]
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = await get_user(user.id)
    last_bonus = user_data['last_bonus'] if user_data else None

    if last_bonus != today:
        await add_balance(user.id, 2500)
        await conn.execute("UPDATE users SET last_bonus = $1 WHERE user_id = $2", today, user.id)
        await conn.close()
        balance = await get_balance(user.id)
        await update.message.reply_text(f"🎉 Бонус! +2500 COINS\n💰 Баланс: {balance}")

    balance = await get_balance(user.id)
    await update.message.reply_text(
        f"🏰 Добро пожаловать в CoinFlow!\n💰 Баланс: {balance} COINS",
        reply_markup=main_keyboard if user.id != ADMIN_ID else admin_keyboard
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
    if not tasks:
        await update.message.reply_text("📭 Сейчас нет заданий.")
        return
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
            return

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
        await update.message.reply_text("✅ Сообщение отправлено!")
        context.user_data['support_mode'] = False
        await start(update, context)

# Покупка COINS
async def buy_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("500 COINS - 50 ⭐", callback_data="buy_500")],
        [InlineKeyboardButton("1500 COINS - 150 ⭐", callback_data="buy_1500")],
        [InlineKeyboardButton("3000 COINS - 300 ⭐", callback_data="buy_3000")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    await update.message.reply_text("💳 Пополни баланс COINS за Telegram Stars:", reply_markup=keyboard)

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back":
        await start(update, context)
        return
    if query.data.startswith("buy_"):
        stars = int(query.data.replace("buy_", ""))
        amount_map = {500: 500, 1500: 1500, 3000: 3000}
        amount = amount_map[stars]
        await context.bot.send_invoice(
            chat_id=update.effective_user.id,
            title="Пополнение COINS",
            description=f"{amount} COINS на баланс",
            payload=f"coins_{amount}",
            currency="XTR",
            prices=[{"label": f"{amount} COINS", "amount": stars}]
        )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    amount = int(payload.replace("coins_", ""))
    await add_balance(update.effective_user.id, amount)
    await update.message.reply_text(f"✅ Пополнение успешно! +{amount} COINS")

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
    user_id = update.effective_user.id

    if text == "📊 Мой кабинет":
        await my_cabinet(update, context)
    elif text == "🤑 Заработать":
        await earn(update, context)
    elif text == "📞 Поддержка":
        await support(update, context)
    elif text == "💳 Пополнить":
        await buy_coins(update, context)
    elif context.user_data.get('support_mode') and user_id != ADMIN_ID:
        await support_message(update, context)
    elif user_id == ADMIN_ID and text in ["📊 Статистика", "📢 Рассылка", "💰 Выдать монеты", "📝 Управление заданиями", "🔙 Выйти из админки"]:
        await update.message.reply_text("⏳ Админ-функции в разработке для этого кода.")
    elif user_id == ADMIN_ID and text == "👑 Админка":
        await admin_panel(update, context)
    else:
        await update.message.reply_text("⏳ В разработке")

async def main():
    await init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(task_handler))
    application.add_handler(CallbackQueryHandler(buy_handler, pattern="^buy_"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Бот запущен с PostgreSQL и платежами")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
