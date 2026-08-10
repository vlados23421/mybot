import os
import asyncio
from aiohttp import web
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler

from database import init_db, get_user, register_user, add_balance, get_balance, add_purchase, create_promo, validate_promo, use_promo, get_purchases

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

main_keyboard = ReplyKeyboardMarkup([
    ["⭐ Купить звёзды", "📦 История"],
    ["📝 Отзывы", "📞 Поддержка"],
    ["👑 Админка"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "💰 Пополнить баланс"],
    ["🎟️ Создать промокод", "📜 История операций"],
    ["🔙 Выйти из админки"]
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_db()
    user = update.effective_user
    user_id = user.id
    username = user.username or "Пользователь"
    
    user_data = await get_user(user_id)
    is_new = user_data is None
    
    await register_user(user_id, username)
    balance = await get_balance(user_id)
    user_data = await get_user(user_id)
    
    if is_new:
        await update.message.reply_text(
            f"🌟 **Добро пожаловать в StarWaves!** 🎉\n\n"
            f"Ты только что присоединился к нашему сообществу!\n"
            f"💰 Твой баланс: {balance} TRX\n"
            f"⭐ Всего звёзд: {user_data['total_stars']}\n\n"
            f"Здесь ты можешь купить Telegram Stars по лучшей цене.\n"
            f"📌 Подпишись на наш канал: @CoinFlowNews",
            parse_mode='Markdown',
            reply_markup=main_keyboard
        )
    else:
        await update.message.reply_text(
            f"🌟 **Добро пожаловать в StarWaves!**\n\n"
            f"💰 Твой баланс: {balance} TRX\n"
            f"⭐ Всего звёзд: {user_data['total_stars']}\n\n"
            f"Здесь ты можешь купить Telegram Stars по лучшей цене.",
            parse_mode='Markdown',
            reply_markup=main_keyboard
        )

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
        price = stars  # 1 звезда = 1 XTR
        await context.bot.send_invoice(
            chat_id=update.effective_user.id,
            title=f"{stars} ⭐",
            description=f"Покупка {stars} звёзд в StarWaves",
            payload=f"stars_{stars}",
            currency="XTR",
            prices=[{"label": f"{stars} Stars", "amount": price}]
        )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    stars = int(payload.replace("stars_", ""))
    user_id = update.effective_user.id
    await add_purchase(user_id, stars, stars)
    await update.message.reply_text(
        f"✅ **Покупка завершена!**\n"
        f"⭐ {stars} звёзд зачислены на твой баланс.\n"
        f"💰 Оплачено: {stars} XTR",
        parse_mode='Markdown'
    )

# ===== АДМИНКА =====
async def adminka_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа")
        return
    await update.message.reply_text(
        "👑 **Админ-панель**\n\n"
        "Выбери действие:",
        reply_markup=admin_keyboard,
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "📦 История":
        rows = await get_purchases(user_id)
        if not rows:
            await update.message.reply_text("📭 У тебя пока нет покупок.")
            return
        output = "📦 **История покупок:**\n\n"
        for r in rows:
            output += f"⭐ {r['stars']} звёзд — {r['price']} XTR"
            if r['promo_code']:
                output += f" (промокод: {r['promo_code']})"
            output += "\n"
        await update.message.reply_text(output, parse_mode='Markdown')
        return

    if text == "📝 Отзывы":
        await update.message.reply_text(
            "📝 **Оставь отзыв о StarWaves!**\n\n"
            "Твоё мнение помогает нам становиться лучше!\n"
            "👉 Оставь отзыв здесь: https://forms.gle/твоя_ссылка_на_форму",
            parse_mode='Markdown'
        )
        return

    if text == "📞 Поддержка":
        await update.message.reply_text(
            "📞 **Поддержка StarWaves**\n\n"
            "Если у тебя есть вопросы, проблемы или предложения, свяжись с администратором:\n"
            "👑 @ArchibaldNn",
            parse_mode='Markdown'
        )
        return

    if text == "👑 Админка" and user_id == ADMIN_ID:
        await adminka_command(update, context)
        return

    if user_id == ADMIN_ID:
        if text == "📊 Статистика":
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_stars = await conn.fetchval("SELECT SUM(total_stars) FROM users") or 0
            total_balance = await conn.fetchval("SELECT SUM(balance) FROM users") or 0
            await conn.close()
            await update.message.reply_text(
                f"📊 **Статистика:**\n\n"
                f"👥 Пользователей: {total_users}\n"
                f"⭐ Продано звёзд: {total_stars}\n"
                f"💰 Баланс системы: {total_balance} XTR",
                parse_mode='Markdown'
            )
            return
        if text == "💰 Пополнить баланс":
            await update.message.reply_text(
                "💰 **Введи ID пользователя и сумму через пробел:**\n"
                "Пример: 123456789 5.0"
            )
            context.user_data['admin_balance_mode'] = True
            return
        if text == "🎟️ Создать промокод":
            await update.message.reply_text(
                "🎟️ **Введи данные промокода через пробел:**\n"
                "Формат: КОД СКИДКА [ЛИМИТ]\n"
                "Пример: STAR10 10 50"
            )
            context.user_data['admin_promo_mode'] = True
            return
        if text == "📜 История операций":
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            rows = await conn.fetch("SELECT user_id, stars, price, promo_code, created_at FROM purchases ORDER BY created_at DESC LIMIT 10")
            await conn.close()
            if not rows:
                await update.message.reply_text("📭 История операций пуста.")
                return
            output = "📜 **Последние 10 операций:**\n\n"
            for r in rows:
                output += f"👤 {r['user_id']} | ⭐ {r['stars']} | {r['price']} XTR"
                if r['promo_code']:
                    output += f" (промокод: {r['promo_code']})"
                output += "\n"
            await update.message.reply_text(output, parse_mode='Markdown')
            return
        if text == "🔙 Выйти из админки":
            await update.message.reply_text("👋 Выход из админки.", reply_markup=main_keyboard)
            return

    if text.startswith("/ref"):
        user_id = update.effective_user.id
        ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
        await update.message.reply_text(
            f"📤 **Пригласи друга и получи бонус!**\n\n"
            f"Твоя уникальная ссылка:\n`{ref_link}`\n\n"
            f"🔥 Если кто-то перейдёт по твоей ссылке и зарегистрируется,\n"
            f"**оба получат +500 XTR**!",
            parse_mode='Markdown'
        )
        return

    if context.user_data.get('custom_stars'):
        try:
            stars = int(text)
            if stars < 1 or stars > 10000:
                await update.message.reply_text("❌ Введи число от 1 до 10000.")
                return
            price = stars
            context.user_data['custom_stars'] = False
            await context.bot.send_invoice(
                chat_id=update.effective_user.id,
                title=f"{stars} ⭐",
                description=f"Покупка {stars} звёзд в StarWaves",
                payload=f"stars_{stars}",
                currency="XTR",
                prices=[{"label": f"{stars} Stars", "amount": price}]
            )
        except:
            await update.message.reply_text("❌ Введи число!")
        return

    if context.user_data.get('admin_balance_mode') and user_id == ADMIN_ID:
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Неверный формат. Используй: ID Сумма")
            return
        try:
            target_id = int(parts[0])
            amount = float(parts[1])
            await add_balance(target_id, amount)
            context.user_data['admin_balance_mode'] = False
            await update.message.reply_text(f"✅ Баланс пользователя {target_id} пополнен на {amount} XTR.")
        except:
            await update.message.reply_text("❌ Ошибка. Проверь ID и сумму.")
        return

    if context.user_data.get('admin_promo_mode') and user_id == ADMIN_ID:
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Неверный формат. Используй: КОД СКИДКА [ЛИМИТ]")
            return
        code = parts[0].upper()
        try:
            discount = int(parts[1])
            max_uses = int(parts[2]) if len(parts) > 2 else 100
            await create_promo(code, discount, max_uses)
            context.user_data['admin_promo_mode'] = False
            await update.message.reply_text(f"✅ Промокод {code} создан! Скидка: {discount}%, лимит: {max_uses} использований.")
        except:
            await update.message.reply_text("❌ Ошибка. Проверь данные.")
        return

    if text == "⭐ Купить звёзды":
        await buy_stars_menu(update, context)
        return

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
    application.add_handler(CommandHandler("adminka", adminka_command))
    application.add_handler(CommandHandler("ref", handle_message))
    application.add_handler(CallbackQueryHandler(buy_handler, pattern="^(buy_|custom|back_main)"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 StarWaves с реальной оплатой через Google Play запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await start_web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
