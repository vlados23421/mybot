import os
import asyncio
import asyncpg
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# === БАЗА ДАННЫХ (PostgreSQL) ===
async def init_db():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS star_purchases (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            stars_amount INTEGER,
            price_usd INTEGER,
            purchase_date TEXT
        )
    ''')
    await conn.close()

async def log_purchase(user_id, username, stars, price):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute(
        "INSERT INTO star_purchases (user_id, username, stars_amount, price_usd, purchase_date) VALUES ($1, $2, $3, $4, NOW())",
        user_id, username, stars, price
    )
    await conn.close()

async def get_stats():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    total_purchases = await conn.fetchval("SELECT COUNT(*) FROM star_purchases")
    total_stars = await conn.fetchval("SELECT SUM(stars_amount) FROM star_purchases") or 0
    total_revenue = await conn.fetchval("SELECT SUM(price_usd) FROM star_purchases") or 0
    await conn.close()
    return total_purchases, total_stars, total_revenue

# === КЛАВИАТУРЫ ===
main_keyboard = ReplyKeyboardMarkup([
    ["⭐ Купить звёзды"],
    ["📊 Мои покупки"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика продаж"]
], resize_keyboard=True)

# === СТАРТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_db()
    user = update.effective_user
    await update.message.reply_text(
        f"🌟 **Добро пожаловать в StarWaves!**\n\n"
        f"Здесь ты можешь купить Telegram Stars по лучшей цене.\n"
        f"💰 Оплата происходит в один клик через Telegram.",
        parse_mode='Markdown',
        reply_markup=main_keyboard if user.id != ADMIN_ID else admin_keyboard
    )

# === КУПИТЬ ЗВЁЗДЫ ===
async def buy_stars_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("50 ⭐ - 1$", callback_data="buy_50")],
        [InlineKeyboardButton("150 ⭐ - 3$", callback_data="buy_150")],
        [InlineKeyboardButton("300 ⭐ - 5$", callback_data="buy_300")],
        [InlineKeyboardButton("500 ⭐ - 7.5$", callback_data="buy_500")],
        [InlineKeyboardButton("1000 ⭐ - 15$", callback_data="buy_1000")]
    ])
    await update.message.reply_text(
        "🌟 **Выбери пакет звёзд:**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("buy_"):
        stars = int(data.replace("buy_", ""))
        price_map = {50: 1, 150: 3, 300: 5, 500: 7, 1000: 15}
        price_usd = price_map.get(stars, 1)
        await context.bot.send_invoice(
            chat_id=update.effective_user.id,
            title=f"{stars} ⭐",
            description=f"Покупка {stars} Telegram Stars",
            payload=f"stars_{stars}_{price_usd}",
            currency="XTR",
            prices=[{"label": f"{stars} Stars", "amount": stars}]
        )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split("_")
    stars = int(parts[1])
    price_usd = int(parts[2])
    user = update.effective_user
    await log_purchase(user.id, user.username or "No username", stars, price_usd)
    await update.message.reply_text(
        f"✅ **Покупка успешна!**\n"
        f"⭐ {stars} звёзд зачислено на твой баланс в Telegram.",
        parse_mode='Markdown'
    )

# === МОИ ПОКУПКИ ===
async def my_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch("SELECT stars_amount, price_usd, purchase_date FROM star_purchases WHERE user_id = $1 ORDER BY id DESC", user_id)
    await conn.close()
    if not rows:
        await update.message.reply_text("📭 У тебя пока нет покупок.")
        return
    text = "📊 **История твоих покупок:**\n\n"
    for r in rows:
        text += f"⭐ {r['stars_amount']} звёзд — ${r['price_usd']} ({r['purchase_date'][:19]})\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# === АДМИНКА ===
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_purchases, total_stars, total_revenue = await get_stats()
    await update.message.reply_text(
        f"👑 **Статистика продаж:**\n\n"
        f"📦 Всего покупок: {total_purchases}\n"
        f"⭐ Продано звёзд: {total_stars}\n"
        f"💰 Выручка: ${total_revenue}",
        parse_mode='Markdown'
    )

# === ОБРАБОТЧИК ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if text == "⭐ Купить звёзды":
        await buy_stars_menu(update, context)
    elif text == "📊 Мои покупки":
        await my_purchases(update, context)
    elif text == "📊 Статистика продаж" and user_id == ADMIN_ID:
        await admin_stats(update, context)

# === ВЕБ-СЕРВЕР ===
async def health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Веб-сервер запущен на порту {port}")

# === ЗАПУСК ===
async def main():
    await init_db()
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(buy_handler, pattern="^buy_"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 StarWaves Bot запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await start_web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
