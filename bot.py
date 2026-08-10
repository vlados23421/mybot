import os
import asyncio
from random import randint
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from database import (
    init_db, get_player, create_player, update_player_stats,
    get_top_players, get_total_players,
    get_guild, get_guild_by_leader, create_guild, join_guild,
    get_guild_members, get_top_guilds, add_pvp_battle
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = "@CoinFlowNews"

# ===== КЛАВИАТУРЫ =====
main_keyboard = ReplyKeyboardMarkup([
    ["🧙 Профиль", "⚔️ Квесты"],
    ["🏆 Гильдии", "⚡ PvP"],
    ["📢 Ивенты", "📞 Поддержка"]
], resize_keyboard=True)

# ===== СТАРТ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_db()
    user = update.effective_user
    await create_player(user.id, user.username or "Без имени")
    player = await get_player(user.id)
    guild = None
    if player['guild_id']:
        guild = await get_guild(player['guild_id'])
    
    text = f"⚔️ **Добро пожаловать в мир приключений!**\n\n"
    text += f"🧙 Уровень: {player['level']}\n"
    text += f"⭐ Опыт: {player['exp']} / {player['level'] * 100}\n"
    text += f"💰 Золото: {player['gold']}\n"
    text += f"⚡ Энергия: {player['energy']}\n"
    if guild:
        text += f"🏆 Гильдия: {guild['name']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard)

# ===== ПРОФИЛЬ =====
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await get_player(update.effective_user.id)
    guild = None
    if player['guild_id']:
        guild = await get_guild(player['guild_id'])
    text = f"🧙 **Твой профиль**\n\n"
    text += f"👤 Имя: {player['username']}\n"
    text += f"📈 Уровень: {player['level']}\n"
    text += f"⭐ Опыт: {player['exp']} / {player['level'] * 100}\n"
    text += f"💰 Золото: {player['gold']}\n"
    text += f"⚡ Энергия: {player['energy']}\n"
    if guild:
        text += f"🏆 Гильдия: {guild['name']}\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ===== КВЕСТЫ =====
async def quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌲 Поход в лес", callback_data="quest_1")],
        [InlineKeyboardButton("🏔️ Подземелье", callback_data="quest_2")],
        [InlineKeyboardButton("🔄 Восстановить энергию", callback_data="restore")]
    ])
    await update.message.reply_text(
        "⚔️ **Выбери квест:**\n\n"
        "🌲 Поход в лес — +50 опыта, +20 золота (20 энергии)\n"
        "🏔️ Подземелье — +100 опыта, +50 золота (40 энергии)",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def quest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    player = await get_player(user_id)
    
    if data == "restore":
        await query.edit_message_text("⚡ Энергия восстановлена! (заглушка)")
        return
    
    cost = 20 if data == "quest_1" else 40
    if player['energy'] < cost:
        await query.edit_message_text("❌ Недостаточно энергии! Нажми «Восстановить».")
        return
    
    exp = 50 if data == "quest_1" else 100
    gold = 20 if data == "quest_1" else 50
    await update_player_stats(user_id, exp, gold, cost)
    player = await get_player(user_id)
    await query.edit_message_text(
        f"✅ **Квест выполнен!**\n"
        f"⭐ +{exp} опыта\n"
        f"💰 +{gold} золота\n"
        f"📈 Уровень: {player['level']}\n"
        f"⚡ Осталось энергии: {player['energy']}"
    )

# ===== ГИЛЬДИИ =====
async def guilds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать гильдию", callback_data="guild_create")],
        [InlineKeyboardButton("📋 Топ гильдий", callback_data="guild_top")]
    ])
    await update.message.reply_text(
        "🏆 **Гильдии:**\n\nСоздай свою гильдию или вступи в топовую!",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def guild_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data == "guild_create":
        await query.edit_message_text(
            "🏆 **Введи название гильдии:**\n\n"
            "Например: «Драконы»"
        )
        context.user_data['creating_guild'] = True
        return
    
    if data == "guild_top":
        top = await get_top_guilds()
        text = "📋 **Топ гильдий:**\n\n"
        for i, g in enumerate(top[:5], 1):
            text += f"{i}. {g['name']} — {g['members']} участников\n"
        await query.edit_message_text(text, parse_mode='Markdown')

async def create_guild_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('creating_guild'):
        name = update.message.text
        user_id = update.effective_user.id
        guild_id = await create_guild(name, user_id)
        context.user_data['creating_guild'] = False
        await update.message.reply_text(f"🏆 Гильдия **{name}** создана! ID: {guild_id}")

# ===== PVP =====
async def pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = None  # Используем базу данных через функции
    opponents = None  # Временно убираем поиск для стабильности
    await update.message.reply_text("⚡ PvP-арена будет доступна в следующем обновлении!")
    return

# ===== ИВЕНТЫ =====
async def events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = await get_total_players()
    await update.message.reply_text(
        f"📢 **Ивенты:**\n\n"
        f"🔥 Эпический квест этой недели: «Охота на дракона»\n"
        f"👥 Выполни квест в канале и получи эксклюзивный скин!\n\n"
        f"📊 Всего игроков: {total}"
    )

# ===== ОБРАБОТЧИК =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🧙 Профиль":
        await profile(update, context)
    elif text == "⚔️ Квесты":
        await quests(update, context)
    elif text == "🏆 Гильдии":
        await guilds(update, context)
    elif text == "⚡ PvP":
        await pvp(update, context)
    elif text == "📢 Ивенты":
        await events(update, context)
    elif text == "📞 Поддержка":
        await update.message.reply_text("📞 Свяжись с администратором: @ArchibaldNn")
    elif context.user_data.get('creating_guild'):
        await create_guild_handler(update, context)

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
    application.add_handler(CallbackQueryHandler(quest_handler, pattern="^(quest_|restore)"))
    application.add_handler(CallbackQueryHandler(guild_handler, pattern="^guild_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await start_web_server()
    print("🚀 Игровой бот запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
