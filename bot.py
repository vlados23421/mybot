import os
import asyncio
import asyncpg
import aiohttp
import hmac
import hashlib
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ===== ТВОИ КЛЮЧИ ОТ NOWPAYMENTS =====
NOW_API_KEY = "NP8C82P-3JYMAGP-K0ZN9E3-7FTWCYZ"
NOW_IPN_KEY = "eBzfV4qylMwLzjVGCr4n4yxOgJ+q/R+R"

# ===== БАЗА ДАННЫХ =====
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

# ===== КЛАВИАТУРЫ =====
main_keyboard = ReplyKeyboardMarkup([
    ["⭐ Купить звёзды"],
    ["📊 Мои покупки"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика продаж"]
], resize_keyboard=True)

# ===== СТАРТ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_db()
    user = update.effective_user
    await update.message.reply_text(
        f"🌟 **Добро пожаловать в StarWaves!**\n\n"
        f"Здесь ты можешь купить Telegram Stars по лучшей цене.\n"
        f"💰 Оплата происходит через криптовалюту (USDT) в один клик.",
        parse_mode='Markdown',
        reply_markup=main_keyboard if user.id != ADMIN_ID else admin_keyboard
    )

# ===== КУПИТЬ ЗВЁЗДЫ (через NOWPayments) =====
async def buy_stars_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("50 ⭐ - 1.0 USDT", callback_data="buy_50")],
        [InlineKeyboardButton("150 ⭐ - 3.0 USDT", callback_data="buy_150")],
        [InlineKeyboardButton("300 ⭐ - 5.0 USDT", callback_data="buy_300")],
        [InlineKeyboardButton("500 ⭐ - 7.5 USDT", callback_data="buy_500")],
        [InlineKeyboardButton("1000 ⭐ - 15.0 USDT", callback_data="buy_1000")]
    ])
    await update.message.reply_text(
        "🌟 **Выбери пакет звёзд и оплати в USDT:**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("buy_"):
        stars = int(data.replace("buy_", ""))
        price_map = {50: 1.0, 150: 3.0, 300: 5.0, 500: 7.5, 1000: 15.0}
        price = price_map[stars]
        
        # Создаём счёт в NOWPayments
        async with aiohttp.ClientSession() as session:
            headers = {"x-api-key": NOW_API_KEY, "Content-Type": "application/json"}
            payload = {
                "price_amount": price,
                "price_currency": "usd",
                "pay_currency": "usdt",
                "ipn_callback_url": f"https://{os.getenv('RENDER_EXTERNAL_URL')}/ipn",
                "order_id": f"stars_{stars}_{update.effective_user.id}",
                "order_description": f"Покупка {stars} Telegram Stars"
            }
            async with session.post("https://api.nowpayments.io/v1/invoice", headers=headers, json=payload) as resp:
                result = await resp.json()
                if "invoice_url" in result:
                    await query.edit_message_text(
                        f"💳 **Счёт создан!**\n\n"
                        f"💰 Сумма: {price} USDT\n"
                        f"⭐ Звёзды: {stars}\n\n"
                        f"Перейдите по ссылке ниже, чтобы оплатить:",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("💳 Перейти к оплате", url=result["invoice_url"])],
                            [InlineKeyboardButton("🔄 Я оплатил (Проверить)", callback_data=f"check_{result['id']}_{stars}")]
                        ])
                    )
                else:
                    await query.edit_message_text(f"❌ Ошибка создания счета: {result}")

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("check_"):
        _, invoice_id, stars = data.split("_")
        
        async with aiohttp.ClientSession() as session:
            headers = {"x-api-key": NOW_API_KEY}
            async with session.get(f"https://api.nowpayments.io/v1/invoice/{invoice_id}") as resp:
                result = await resp.json()
                if result.get("invoice_status") == "paid":
                    user_id = update.effective_user.id
                    username = update.effective_user.username or "No username"
                    await log_purchase(user_id, username, int(stars), result.get("price_amount"))
                    await query.edit_message_text(f"✅ **Оплата подтверждена!**\n⭐ {stars} звёзд зачислены на твой баланс в Telegram.")
                else:
                    await query.edit_message_text(f"⏳ Оплата ещё не поступила. Статус: {result.get('invoice_status')}. Нажми «Проверить» позже.")

# ===== МОИ ПОКУПКИ =====
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

# ===== АДМИНКА =====
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

# ===== IPN WEBHOOK (для NOWPayments) =====
async def ipn_webhook(request):
    try:
        data = await request.json()
        # Проверяем подпись IPN
        provided_sig = request.headers.get('x-nowpayments-sig')
        computed_sig = hmac.new(NOW_IPN_KEY.encode(), str(data).encode(), hashlib.sha512).hexdigest()
        if provided_sig != computed_sig:
            return web.Response(text="Invalid signature", status=403)
        
        if data.get("payment_status") == "confirmed" or data.get("payment_status") == "finished":
            order_id = data.get("order_id")
            if order_id and order_id.startswith("stars_"):
                parts = order_id.split("_")
                stars = int(parts[1])
                user_id = int(parts[2])
                conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
                await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", stars, user_id)
                await conn.close()
                return web.Response(text="OK")
        return web.Response(text="OK")
    except:
        return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_post('/ipn', ipn_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Веб-сервер запущен на порту {port}")

async def health_check(request):
    return web.Response(text="OK")

# ===== ЗАПУСК =====
async def main():
    await init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(buy_handler, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(check_payment, pattern="^check_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 StarWaves with NOWPayments запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await start_web_server()
    await asyncio.Event().wait()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if text == "⭐ Купить звёзды":
        await buy_stars_menu(update, context)
    elif text == "📊 Мои покупки":
        await my_purchases(update, context)
    elif text == "📊 Статистика продаж" and user_id == ADMIN_ID:
        await admin_stats(update, context)

if __name__ == "__main__":
    asyncio.run(main())
