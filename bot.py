import os
import asyncio
import asyncpg
import aiohttp
import json
import hashlib
from datetime import datetime, timedelta
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ===== БАЗА ДАННЫХ =====
async def init_db():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            username TEXT,
            balance DECIMAL DEFAULT 0,
            total_stars INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            stars INTEGER,
            price DECIMAL,
            promo_code TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            discount DECIMAL DEFAULT 10,
            max_uses INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await conn.close()

async def get_user(user_id):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return user

async def register_user(user_id, username):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute('''
        INSERT INTO users (user_id, username) VALUES ($1, $2)
        ON CONFLICT (user_id) DO NOTHING
    ''', user_id, username)
    await conn.close()

async def add_balance(user_id, amount):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)
    await conn.close()

async def get_balance(user_id):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    res = await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return res or 0

async def add_purchase(user_id, stars, price, promo=None):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute(
        "INSERT INTO purchases (user_id, stars, price, promo_code) VALUES ($1, $2, $3, $4)",
        user_id, stars, price, promo
    )
    await conn.execute("UPDATE users SET total_stars = total_stars + $1 WHERE user_id = $2", stars, user_id)
    await conn.close()

# ===== ПРОМОКОДЫ =====
async def create_promo(code, discount, max_uses=100):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute(
        "INSERT INTO promo_codes (code, discount, max_uses) VALUES ($1, $2, $3)",
        code, discount, max_uses
    )
    await conn.close()

async def validate_promo(code):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    promo = await conn.fetchrow("SELECT * FROM promo_codes WHERE code = $1 AND active = TRUE", code)
    await conn.close()
    if not promo:
        return None
    if promo['used_count'] >= promo['max_uses']:
        return None
    return promo

async def use_promo(code):
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = $1", code)
    await conn.close()

# ===== КЛАВИАТУРЫ =====
main_keyboard = ReplyKeyboardMarkup([
    ["⭐ Купить звёзды", "📦 История"],
    ["👑 Админка", "📞 Поддержка"]
], resize_keyboard=True)

# ===== СТАРТ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_db()
    user = update.effective_user
    await register_user(user.id, user.username)
    balance = await get_balance(user.id)
    await update.message.reply_text(
        f"🌟 **Добро пожаловать в StarWaves!**\n\n"
        f"💰 Твой баланс: {balance} TRX\n"
        f"⭐ Всего звёзд: {await get_user(user.id)['total_stars']}\n\n"
        f"Здесь ты можешь купить Telegram Stars по лучшей цене.",
        parse_mode='Markdown',
        reply_markup=main_keyboard if user.id != ADMIN_ID else admin_keyboard
    )

# ===== КУПИТЬ ЗВЁЗДЫ (гибкий ввод) =====
async def buy_stars_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 50 звёзд (1.0 TRX)", callback_data="buy_50")],
        [InlineKeyboardButton("⭐ 150 звёзд (3.0 TRX)", callback_data="buy_150")],
        [InlineKeyboardButton("⭐ 300 звёзд (5.0 TRX)", callback_data="buy_300")],
        [InlineKeyboardButton("⭐ 500 звёзд (7.5 TRX)", callback_data="buy_500")],
        [InlineKeyboardButton("⭐ 1000 звёзд (15.0 TRX)", callback_data="buy_1000")],
        [InlineKeyboardButton("✏️ Своё количество", callback_data="custom")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])
    await update.message.reply_text(
        "🌟 **Выбери пакет или введи своё количество:**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_main":
        await start(update, context)
        return
    
    if data == "custom":
        await query.edit_message_text(
            "✏️ **Введи количество звёзд, которое хочешь купить:**\n\n"
            "Например: 200\n"
            "Цена будет рассчитана автоматически.",
            parse_mode='Markdown'
        )
        context.user_data['custom_stars'] = True
        return
    
    if data.startswith("buy_"):
        stars = int(data.replace("buy_", ""))
        price = round(stars * 0.02, 2)  # 0.02 TRX за звезду
        await query.edit_message_text(
            f"💰 **К оплате:** {price} TRX\n"
            f"⭐ Звёзды: {stars}\n\n"
            f"Есть промокод? Введи его через пробел после цены.",
            parse_mode='Markdown'
        )
        context.user_data['pending_purchase'] = {"stars": stars, "price": price}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Обработка истории
    if text == "📦 История":
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        rows = await conn.fetch("SELECT stars, price, promo_code, created_at FROM purchases WHERE user_id = $1 ORDER BY created_at DESC", user_id)
        await conn.close()
        if not rows:
            await update.message.reply_text("📭 У тебя пока нет покупок.")
            return
        text = "📦 **История покупок:**\n\n"
        for r in rows[:5]:
            text += f"⭐ {r['stars']} звёзд — {r['price']} TRX"
            if r['promo_code']:
                text += f" (промокод: {r['promo_code']})"
            text += f"\n"
        await update.message.reply_text(text, parse_mode='Markdown')
        return

    # Обработка админских команд
    if user_id == ADMIN_ID:
        if text.startswith("/addbalance"):
            parts = text.split()
            if len(parts) == 3:
                try:
                    target_id = int(parts[1])
                    amount = float(parts[2])
                    await add_balance(target_id, amount)
                    await update.message.reply_text(f"✅ Баланс пользователя {target_id} пополнен на {amount} TRX.")
                except:
                    await update.message.reply_text("❌ Ошибка. Используй: /addbalance ID сумма")
            else:
                await update.message.reply_text("❌ Используй: /addbalance ID сумма")
            return

        if text.startswith("/createpromo"):
            parts = text.split()
            if len(parts) == 3 or len(parts) == 4:
                code = parts[1].upper()
                try:
                    discount = int(parts[2])
                    max_uses = int(parts[3]) if len(parts) == 4 else 100
                    await create_promo(code, discount, max_uses)
                    await update.message.reply_text(f"✅ Промокод {code} создан! Скидка: {discount}%, можно использовать {max_uses} раз.")
                except:
                    await update.message.reply_text("❌ Ошибка. Используй: /createpromo КОД СКИДКА [МАКС_ИСПОЛЬЗОВАНИЙ]")
            else:
                await update.message.reply_text("❌ Используй: /createpromo КОД СКИДКА [МАКС_ИСПОЛЬЗОВАНИЙ]")
            return

    # Обработка кастомного ввода звёзд
    if context.user_data.get('custom_stars'):
        try:
            stars = int(text)
            if stars < 1 or stars > 10000:
                await update.message.reply_text("❌ Введи число от 1 до 10000.")
                return
            price = round(stars * 0.02, 2)
            context.user_data['custom_stars'] = False
            context.user_data['pending_purchase'] = {"stars": stars, "price": price}
            await update.message.reply_text(
                f"💰 **К оплате:** {price} TRX\n"
                f"⭐ Звёзды: {stars}\n\n"
                f"Есть промокод? Введи его через пробел после цены.",
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text("❌ Введи число!")
        return

    # Обработка оплаты с промокодом
    if context.user_data.get('pending_purchase'):
        parts = text.split()
        try:
            price = float(parts[0])
            promo = parts[1] if len(parts) > 1 else None
            if promo:
                promo_data = await validate_promo(promo)
                if promo_data:
                    discount = promo_data['discount']
                    price = price * (1 - discount / 100)
                    await use_promo(promo)
                else:
                    await update.message.reply_text("❌ Промокод недействителен.")
                    return
            stars = context.user_data['pending_purchase']['stars']
            await add_purchase(user_id, stars, price, promo)
            context.user_data['pending_purchase'] = None
            await update.message.reply_text(
                f"✅ **Покупка завершена!**\n"
                f"⭐ {stars} звёзд зачислены на твой баланс.\n"
                f"💰 Списано: {price} TRX\n"
                f"📦 Промокод: {promo if promo else 'не использован'}",
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text("❌ Введи сумму и промокод через пробел. Пример: 5.0 PROMO10")
        context.user_data['pending_purchase'] = None
        return

    # Обычные кнопки
    if text == "⭐ Купить звёзды":
        await buy_stars_menu(update, context)
    elif text == "📞 Поддержка":
        await update.message.reply_text("📞 **Поддержка StarWaves**\n\nСвяжись с администратором: @ArchibaldNn")
    elif text == "👑 Админка" and user_id == ADMIN_ID:
        await update.message.reply_text(
            "👑 **Админ-панель StarWaves**\n\n"
            "Доступные команды:\n"
            "/addbalance ID сумма — пополнить баланс пользователя\n"
            "/createpromo КОД СКИДКА [МАКС] — создать промокод"
        )

# ===== ВЕБ-СЕРВЕР =====
async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Веб-сервер запущен на порту {port}")

async def main():
    await init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(buy_handler, pattern="^(buy_|custom|back_main)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 StarWaves запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await start_web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
