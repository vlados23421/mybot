import os
import asyncio
import asyncpg
from datetime import datetime, timedelta
from random import randint
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from database import (
    init_db, get_player, create_player, update_player_stats, get_total_players,
    get_guild, create_guild, get_top_guilds,
    create_promo_code, use_promo_code,
    set_cooldown, check_cooldown
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ===== АНТИ-ФЛУД =====
flood_control = {}

async def check_flood(user_id):
    now = datetime.now()
    if user_id in flood_control:
        if (now - flood_control[user_id]).seconds < 2:
            return True
    flood_control[user_id] = now
    return False

# ===== КЛАВИАТУРЫ =====
main_keyboard = ReplyKeyboardMarkup([
    ["🧙 Профиль", "⚔️ Квесты"],
    ["🏆 Гильдии", "⚡ PvP"],
    ["📢 Ивенты", "📞 Поддержка"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "💰 Выдать золото"],
    ["⭐ Выдать опыт", "⚡ Восстановить энергию"],
    ["📋 Список игроков", "🎟️ Создать промокод"],
    ["🔙 Выйти из админки"]
], resize_keyboard=True)

# ===== СТАРТ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    await init_db()
    user = update.effective_user
    await create_player(user.id, user.username or "Без имени")
    player = await get_player(user.id)
    guild = None
    if player['guild_id']:
        guild = await get_guild(player['guild_id'])
    
    text = f"⚔️ **Добро пожаловать в мир приключений!**\n\n"
    text += f"🧙 **Уровень:** {player['level']}\n"
    text += f"⭐ **Опыт:** {player['exp']} / {player['level'] * 100}\n"
    text += f"💰 **Золото:** {player['gold']}\n"
    text += f"⚡ **Энергия:** {player['energy']}\n"
    if guild:
        text += f"🏆 **Гильдия:** {guild['name']}\n"
    
    if user.id == ADMIN_ID:
        await update.message.reply_text(text + "\n\n👑 **Режим админа активен**", parse_mode='Markdown', reply_markup=admin_keyboard)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard)

# ===== АДМИНКА =====
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    players = await conn.fetchval("SELECT COUNT(*) FROM players")
    guilds = await conn.fetchval("SELECT COUNT(*) FROM guilds")
    pvps = await conn.fetchval("SELECT COUNT(*) FROM pvp_history")
    await conn.close()
    await update.message.reply_text(
        f"📊 **Статистика сервера:**\n\n"
        f"👥 **Игроков:** {players}\n"
        f"🏆 **Гильдий:** {guilds}\n"
        f"⚔️ **PvP боёв:** {pvps}",
        parse_mode='Markdown'
    )

async def admin_gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    await update.message.reply_text("💰 **Введи ID и количество золота через пробел:**\n\nПример: `123456789 500`", parse_mode='Markdown')
    context.user_data['admin_gold'] = True

async def admin_exp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    await update.message.reply_text("⭐ **Введи ID и количество опыта через пробел:**\n\nПример: `123456789 100`", parse_mode='Markdown')
    context.user_data['admin_exp'] = True

async def admin_energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    await update.message.reply_text("⚡ **Введи ID для восстановления энергии:**", parse_mode='Markdown')
    context.user_data['admin_energy'] = True

async def admin_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch("SELECT username, level, gold FROM players ORDER BY level DESC, gold DESC LIMIT 10")
    await conn.close()
    text = "📋 **Топ-10 игроков:**\n\n"
    for i, r in enumerate(rows, 1):
        text += f"{i}. **{r['username']}** — Уровень {r['level']}, {r['gold']} 🪙\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    await update.message.reply_text(
        "🎟️ **Создать промокод**\n\n"
        "Формат: `КОД ТИП КОЛИЧЕСТВО [ИСПОЛЬЗОВАНИЙ]`\n"
        "**Тип:** `gold` или `exp`\n"
        "Пример: `GOLD10 gold 100 5`\n",
        parse_mode='Markdown'
    )
    context.user_data['admin_promo'] = True

async def admin_promo_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 3:
        await update.message.reply_text("❌ **Неверный формат.** Используй: `КОД ТИП КОЛИЧЕСТВО [ИСПОЛЬЗОВАНИЙ]`", parse_mode='Markdown')
        return
    code = parts[0].upper()
    rtype = parts[1]
    amount = int(parts[2])
    uses = int(parts[3]) if len(parts) > 3 else 1
    if rtype not in ['gold', 'exp']:
        await update.message.reply_text("❌ **Тип должен быть** `gold` **или** `exp`", parse_mode='Markdown')
        return
    await create_promo_code(code, rtype, amount, uses)
    context.user_data['admin_promo'] = False
    await update.message.reply_text(f"✅ **Промокод `{code}` создан!**\n\n{amount} {rtype}, {uses} использований", parse_mode='Markdown')

# ===== КОМАНДА /PROMO =====
async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ **Используй:** `/promo КОД`", parse_mode='Markdown')
        return
    code = args[0].upper()
    user_id = update.effective_user.id
    result = await use_promo_code(user_id, code)
    if not result:
        await update.message.reply_text("❌ **Промокод недействителен или уже использован.**", parse_mode='Markdown')
        return
    await update.message.reply_text(f"🎉 **Промокод активирован!**\n\n+{result['reward_amount']} {result['reward_type']}", parse_mode='Markdown')

# ===== ПРОФИЛЬ =====
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    player = await get_player(update.effective_user.id)
    guild = None
    if player['guild_id']:
        guild = await get_guild(player['guild_id'])
    text = f"🧙 **Твой профиль**\n\n"
    text += f"👤 **Имя:** {player['username']}\n"
    text += f"📈 **Уровень:** {player['level']}\n"
    text += f"⭐ **Опыт:** {player['exp']} / {player['level'] * 100}\n"
    text += f"💰 **Золото:** {player['gold']}\n"
    text += f"⚡ **Энергия:** {player['energy']}\n"
    if guild:
        text += f"🏆 **Гильдия:** {guild['name']}\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ===== КВЕСТЫ =====
async def quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌲 Поход в лес", callback_data="quest_1")],
        [InlineKeyboardButton("🏔️ Подземелье", callback_data="quest_2")],
        [InlineKeyboardButton("🔄 Восстановить энергию", callback_data="restore")]
    ])
    await update.message.reply_text(
        "⚔️ **Выбери квест:**\n\n"
        "🌲 Поход в лес — `+50 ⭐, +20 🪙` (20 ⚡)\n"
        "🏔️ Подземелье — `+100 ⭐, +50 🪙` (40 ⚡)",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def quest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    # Проверка кулдауна
    cd = await check_cooldown(user_id, 'quest')
    if cd:
        await query.edit_message_text(f"⏳ **Подожди {cd} секунд перед следующим квестом!**")
        return
    
    player = await get_player(user_id)
    if data == "restore":
        await query.edit_message_text("⚡ **Энергия восстановлена!**")
        return
    
    cost = 20 if data == "quest_1" else 40
    if player['energy'] < cost:
        await query.edit_message_text("❌ **Недостаточно энергии!** Нажми «Восстановить».")
        return
    
    exp = 50 if data == "quest_1" else 100
    gold = 20 if data == "quest_1" else 50
    await update_player_stats(user_id, exp, gold, cost)
    await set_cooldown(user_id, 'quest', 5)  # КД 5 секунд
    player = await get_player(user_id)
    await query.edit_message_text(
        f"✅ **Квест выполнен!**\n\n"
        f"⭐ +{exp} опыта\n"
        f"🪙 +{gold} золота\n"
        f"📈 **Уровень:** {player['level']}\n"
        f"⚡ **Осталось:** {player['energy']}",
        parse_mode='Markdown'
    )

# ===== ГИЛЬДИИ =====
async def guilds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
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
            "🏆 **Введи название гильдии:**\n\nНапример: «Драконы»",
            parse_mode='Markdown'
        )
        context.user_data['creating_guild'] = True
        return
    
    if data == "guild_top":
        top = await get_top_guilds()
        text = "📋 **Топ гильдий:**\n\n"
        for i, g in enumerate(top[:5], 1):
            text += f"{i}. **{g['name']}** — {g['members']} участников\n"
        await query.edit_message_text(text, parse_mode='Markdown')

async def create_guild_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('creating_guild'):
        name = update.message.text
        user_id = update.effective_user.id
        guild_id = await create_guild(name, user_id)
        context.user_data['creating_guild'] = False
        await update.message.reply_text(f"🏆 **Гильдия «{name}» создана!**\n\nID: {guild_id}", parse_mode='Markdown')

# ===== PVP =====
async def pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    await update.message.reply_text("⚡ **PvP-арена будет доступна в следующем обновлении!**", parse_mode='Markdown')

# ===== ИВЕНТЫ =====
async def events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    total = await get_total_players()
    await update.message.reply_text(
        f"📢 **Ивенты:**\n\n"
        f"🔥 Текущий ивент: «Охота на дракона»\n"
        f"🏆 Следи за промокодами в канале!\n\n"
        f"📊 **Всего игроков:** {total}",
        parse_mode='Markdown'
    )

# ===== ОБРАБОТЧИК =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_flood(update.effective_user.id):
        return
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🧙 Профиль":
        await profile(update, context)
        return
    if text == "⚔️ Квесты":
        await quests(update, context)
        return
    if text == "🏆 Гильдии":
        await guilds(update, context)
        return
    if text == "⚡ PvP":
        await pvp(update, context)
        return
    if text == "📢 Ивенты":
        await events(update, context)
        return
    if text == "📞 Поддержка":
        await update.message.reply_text("📞 **Свяжись с администратором:** @ArchibaldNn", parse_mode='Markdown')
        return

    if user_id == ADMIN_ID:
        if text == "📊 Статистика":
            await admin_stats(update, context)
            return
        if text == "💰 Выдать золото":
            await admin_gold(update, context)
            return
        if text == "⭐ Выдать опыт":
            await admin_exp(update, context)
            return
        if text == "⚡ Восстановить энергию":
            await admin_energy(update, context)
            return
        if text == "📋 Список игроков":
            await admin_top(update, context)
            return
        if text == "🎟️ Создать промокод":
            await admin_promo(update, context)
            return
        if text == "🔙 Выйти из админки":
            await update.message.reply_text("👋 **Выход из админки.**", parse_mode='Markdown', reply_markup=main_keyboard)
            return

    if context.user_data.get('admin_gold'):
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ **Используй:** `ID Сумма`", parse_mode='Markdown')
            return
        try:
            user_id = int(parts[0])
            amount = int(parts[1])
            await update_player_stats(user_id, 0, amount, 0)
            context.user_data['admin_gold'] = False
            await update.message.reply_text(f"✅ **Выдано {amount} 🪙 пользователю {user_id}.**", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ **Ошибка.** Проверь ID.", parse_mode='Markdown')
        return

    if context.user_data.get('admin_exp'):
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ **Используй:** `ID Сумма`", parse_mode='Markdown')
            return
        try:
            user_id = int(parts[0])
            amount = int(parts[1])
            await update_player_stats(user_id, amount, 0, 0)
            context.user_data['admin_exp'] = False
            await update.message.reply_text(f"✅ **Выдано {amount} ⭐ пользователю {user_id}.**", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ **Ошибка.** Проверь ID.", parse_mode='Markdown')
        return

    if context.user_data.get('admin_energy'):
        try:
            user_id = int(text)
            await update_player_stats(user_id, 0, 0, -100)
            context.user_data['admin_energy'] = False
            await update.message.reply_text(f"✅ **Энергия пользователя {user_id} восстановлена.**", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ **Ошибка.** Введи ID.", parse_mode='Markdown')
        return

    if context.user_data.get('admin_promo'):
        await admin_promo_create(update, context)
        return

    if context.user_data.get('creating_guild'):
        await create_guild_handler(update, context)
        return

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
    application.add_handler(CommandHandler("promo", promo_command))
    application.add_handler(CallbackQueryHandler(quest_handler, pattern="^(quest_|restore)"))
    application.add_handler(CallbackQueryHandler(guild_handler, pattern="^guild_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Игровой бот с защитой и кулдаунами запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await start_web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
