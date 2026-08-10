import os
import asyncio
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from database import init_db, get_user, register_user, add_balance, get_balance, add_purchase, create_promo, validate_promo, use_promo, get_purchases

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

main_keyboard = ReplyKeyboardMarkup([
    ["⭐ Купить звёзды", "📦 История"],
    ["👑 Админка", "📞 Поддержка"]
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_db()
    user = update.effective_user
    await register_user(user.id, user.username)
    balance = await get_balance(user.id)
    user_data = await get_user(user.id)
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
        price = round(stars * 0.02, 2)
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

    if text == "📦 История":
        rows = await get_purchases(user_id)
        if not rows:
            await update.message.reply_text("📭 У тебя пока нет покупок.")
            return
        output = "📦 **История покупок:**\n\n"
        for r in rows:
            output += f"⭐ {r['stars']} звёзд — {r['price']} TRX"
            if r['promo_code']:
                output += f" (промокод: {r['promo_code']})"
            output += "\n"
        await update.message.reply_text(output, parse_mode='Markdown')
        return

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
