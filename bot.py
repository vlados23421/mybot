import os
import asyncio
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler

from database import init_db, get_user, register_user, add_balance, get_balance, update_streak, get_active_tasks, is_task_done, mark_task_done, create_payment

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ========== МЕНЮ ==========
main_keyboard = ReplyKeyboardMarkup([
    ["🤑 Заработать", "📊 Мой кабинет"],
    ["📢 Рекламировать", "🧾 Чеки"],
    ["📞 Поддержка", "🤖 Наши боты"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "📢 Рассылка"],
    ["💰 Выдать монеты", "📝 Управление заданиями"],
    ["🔙 Выйти из админки"]
], resize_keyboard=True)

# ========== СТАРТ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = await get_user(user.id)
    last_bonus = user_data['last_bonus']
    balance = await get_balance(user.id)
    
    if last_bonus != today:
        await add_balance(user.id, 2500)
        await context.bot.send_message(user.id, f"🎉 Ежедневный бонус! +2500 COINS\n💰 Баланс: {balance+2500}")
    
    await update.message.reply_text(
        f"🏰 Добро пожаловать в CoinFlow!\n💰 Баланс: {await get_balance(user.id)} COINS",
        reply_markup=main_keyboard
    )

# ========== КАБИНЕТ ==========
async def my_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = await get_balance(user_id)
    await update.message.reply_text(
        f"📊 Мой кабинет\n"
        f"🆔 ID: {user_id}\n"
        f"💰 Баланс: {balance} COINS\n"
        f"🔥 Стрик: {await update_streak(user_id)} дней"
    )

# ========== ЗАРАБОТАТЬ (АВТОМАТИЧЕСКАЯ ПРОВЕРКА) ==========
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
        # === АВТОМАТИЧЕСКАЯ ПРОВЕРКА ===
        tasks = await get_active_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task:
            await query.edit_message_text("❌ Задание не найдено")
            return
        try:
            # Проверка через Telegram API
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
            await query.edit_message_text("❌ Ошибка проверки. Убедись, что канал публичный или ты подписан.")
        return

# ========== ПОДДЕРЖКА (В ОСНОВНОМ БОТЕ) ==========
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 Связь с поддержкой\n\n"
        "Если у тебя есть вопрос, проблема или предложение — напиши сообщение ниже. "
        "Администратор прочитает и ответит в ближайшее время.\n\n"
        "⚠️ Если вопрос срочный — пиши в чат: @PrsAdvertisementMy",
        reply_markup=ReplyKeyboardMarkup([["🔙 В меню"]], resize_keyboard=True)
    )
    context.user_data['support_mode'] = True

async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('support_mode') and update.effective_user.id != ADMIN_ID:
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 Новое сообщение в поддержку от {update.effective_user.id} (@{update.effective_user.username}):\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ Сообщение отправлено! Ожидай ответа.")
        context.user_data['support_mode'] = False
        await start(update, context)

# ========== ПОКУПКА COINS (TELEGRAM STARS) ==========
PRICES = {
    "500": 50,    # 500 COINS за 50 Stars
    "1500": 150,  # 1500 COINS за 150 Stars
    "3000": 300   # 3000 COINS за 300 Stars
}

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
        amount = {500: 500, 1500: 1500, 3000: 3000}[stars]
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
