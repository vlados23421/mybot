import os
import asyncio
import asyncpg
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler, ContextTypes

from database import init_db, get_user, register_user, add_balance, get_balance, get_active_tasks, is_task_done, mark_task_done, get_stats, get_all_users, is_banned, set_ban, add_log, get_logs, set_bonus_amount, get_bonus_amount

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

main_keyboard = ReplyKeyboardMarkup([
    ["🤑 Заработать", "📊 Мой кабинет"],
    ["📞 Поддержка", "💳 Пополнить"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "📋 Список пользователей"],
    ["⚖️ Изменить баланс", "📋 Активные задания"],
    ["📢 Рассылка", "⛔ Забанить / Разбанить"],
    ["📤 Экспорт в файл", "⚙️ Настроить бонус"],
    ["📜 Журнал событий", "🔙 Выйти из админки"]
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    if await is_banned(user.id):
        await update.message.reply_text("⛔ Вы заблокированы.")
        return
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = await get_user(user.id)
    last_bonus = user_data['last_bonus'] if user_data else None
    bonus = await get_bonus_amount()

    if last_bonus != today:
        await add_balance(user.id, bonus)
        await conn.execute("UPDATE users SET last_bonus = $1 WHERE user_id = $2", today, user.id)
        await conn.close()
        balance = await get_balance(user.id)
        await update.message.reply_text(f"🎉 Бонус! +{bonus} COINS\n💰 Баланс: {balance}")

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
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_tasks")])
    await update.message.reply_text(
        "🤑 Доступные задания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    if data == "back_tasks":
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
                await add_log(user_id, "Выполнил задание", task['name'])
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

# ===== АДМИНКА =====
async def adminka_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа")
        return
    await admin_panel(update, context)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа")
        return
    await update.message.reply_text(
        "👑 Панель управления CoinFlow",
        reply_markup=admin_keyboard
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users, total_coins, tasks_done = await get_stats()
    await update.message.reply_text(
        f"📊 Статистика\n"
        f"👥 Пользователей: {total_users}\n"
        f"💰 Всего COINS: {total_coins}\n"
        f"✅ Выполнено заданий: {tasks_done}"
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = await get_all_users()
    text = "📋 Список пользователей:\n\n"
    for u in users:
        text += f"ID: {u['user_id']} | @{u['username']} | {u['first_name']} | {u['balance']} COINS\n"
    if len(users) > 30:
        text += "\n📌 Показаны первые 30 пользователей."
    await update.message.reply_text(text[:4000])

async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "⚖️ Введи ID и сумму через пробел:\nПример: 123456789 500"
    )
    context.user_data['balance_mode'] = True

async def admin_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    tasks = await get_active_tasks()
    if not tasks:
        await update.message.reply_text("📭 Нет активных заданий.")
        return
    text = "📋 Активные задания:\n\n"
    for t in tasks:
        text += f"ID {t['id']}: {t['name']} | {t['reward']} COINS\n"
    await update.message.reply_text(text)

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "📢 Введи текст для рассылки всем пользователям:"
    )
    context.user_data['broadcast_mode'] = True

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "⛔ Введи ID пользователя для бана / разбана:\n"
        "Используй формат: ID ban или ID unban\n"
        "Пример: 123456789 ban"
    )
    context.user_data['ban_mode'] = True

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = await get_all_users()
    text = "📤 Экспорт пользователей:\n\n"
    for u in users:
        text += f"{u['user_id']},{u['username']},{u['first_name']},{u['balance']}\n"
    await update.message.reply_text(text)

async def admin_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "⚙️ Введи новую сумму ежедневного бонуса:\n(Например: 3000)"
    )
    context.user_data['bonus_mode'] = True

async def admin_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    logs = await get_logs(20)
    text = "📜 Последние 20 событий:\n\n"
    for l in logs:
        text += f"{l['time'][:19]} | {l['user_id']} | {l['action']} {l['details']}\n"
    await update.message.reply_text(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Обычные кнопки
    if text == "📊 Мой кабинет":
        await my_cabinet(update, context)
    elif text == "🤑 Заработать":
        await earn(update, context)
    elif text == "📞 Поддержка":
        await support(update, context)
    elif text == "💳 Пополнить":
        await buy_coins(update, context)

    # Админские кнопки
    elif user_id == ADMIN_ID:
        if text == "📊 Статистика":
            await admin_stats(update, context)
        elif text == "📋 Список пользователей":
            await admin_users(update, context)
        elif text == "⚖️ Изменить баланс":
            await admin_balance(update, context)
        elif text == "📋 Активные задания":
            await admin_tasks(update, context)
        elif text == "📢 Рассылка":
            await admin_broadcast(update, context)
        elif text == "⛔ Забанить / Разбанить":
            await admin_ban(update, context)
        elif text == "📤 Экспорт в файл":
            await admin_export(update, context)
        elif text == "⚙️ Настроить бонус":
            await admin_bonus(update, context)
        elif text == "📜 Журнал событий":
            await admin_logs(update, context)
        elif text == "🔙 Выйти из админки":
            await update.message.reply_text("👋 Выход из админки.", reply_markup=main_keyboard)
        else:
            await update.message.reply_text("⏳ Неизвестная команда.")

    # Обработка ввода админа
    elif context.user_data.get('balance_mode') and user_id == ADMIN_ID:
        try:
            parts = text.split()
            target_id = int(parts[0])
            amount = int(parts[1])
            await add_balance(target_id, amount)
            await add_log(user_id, "Изменил баланс", f"{target_id}: {amount}")
            await update.message.reply_text(f"✅ Баланс {target_id} изменён на {amount}")
        except:
            await update.message.reply_text("❌ Ошибка! Используй: ID Сумма")
        context.user_data['balance_mode'] = False

    elif context.user_data.get('broadcast_mode') and user_id == ADMIN_ID:
        users = await get_all_users()
        sent = 0
        for u in users:
            try:
                await context.bot.send_message(u['user_id'], f"📢 Админ-рассылка:\n\n{text}")
                sent += 1
            except:
                pass
        await add_log(user_id, "Сделал рассылку", f"{sent} пользователей")
        await update.message.reply_text(f"✅ Рассылка отправлена! {sent} человек.")
        context.user_data['broadcast_mode'] = False

    elif context.user_data.get('ban_mode') and user_id == ADMIN_ID:
        try:
            parts = text.split()
            target_id = int(parts[0])
            action = parts[1].lower()
            if action == "ban":
                await set_ban(target_id, True)
                await add_log(user_id, "Забанил", str(target_id))
                await update.message.reply_text(f"⛔ Пользователь {target_id} забанен.")
            elif action == "unban":
                await set_ban(target_id, False)
                await add_log(user_id, "Разбанил", str(target_id))
                await update.message.reply_text(f"✅ Пользователь {target_id} разбанен.")
            else:
                await update.message.reply_text("❌ Используй: ID ban или ID unban")
        except:
            await update.message.reply_text("❌ Ошибка! Используй: ID ban или ID unban")
        context.user_data['ban_mode'] = False

    elif context.user_data.get('bonus_mode') and user_id == ADMIN_ID:
        try:
            new_bonus = int(text)
            await set_bonus_amount(new_bonus)
            await add_log(user_id, "Изменил бонус", str(new_bonus))
            await update.message.reply_text(f"✅ Бонус изменён на {new_bonus} COINS")
        except:
            await update.message.reply_text("❌ Введи число!")
        context.user_data['bonus_mode'] = False

    else:
        await update.message.reply_text("⏳ В разработке")

# Остальные функции (поддержка, покупка) оставляем без изменений...
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

async def buy_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("500 COINS - 50 ⭐", callback_data="buy_500")],
        [InlineKeyboardButton("1500 COINS - 150 ⭐", callback_data="buy_1500")],
        [InlineKeyboardButton("3000 COINS - 300 ⭐", callback_data="buy_3000")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_buy")]
    ])
    await update.message.reply_text("💳 Пополни баланс COINS за Telegram Stars:", reply_markup=keyboard)

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_buy":
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
    await add_log(update.effective_user.id, "Купил COINS", f"+{amount}")
    await update.message.reply_text(f"✅ Пополнение успешно! +{amount} COINS")

# ===== ЗАПУСК =====
async def main():
    await init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adminka", adminka_command))
    application.add_handler(CallbackQueryHandler(task_handler, pattern="^(do_|back_tasks)"))
    application.add_handler(CallbackQueryHandler(buy_handler, pattern="^(buy_|back_buy)"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 CoinFlow с полной админкой запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
