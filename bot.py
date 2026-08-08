import os
import asyncio
import asyncpg
from datetime import datetime
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from database import init_db, get_user, register_user, add_balance, get_balance, get_active_tasks, is_task_done, mark_task_done, get_stats, get_all_users, is_banned, set_ban, add_log, get_logs, get_bonus_amount, set_bonus_amount, get_maintenance_mode, set_maintenance_mode, get_maintenance_message, create_verify_request, get_pending_requests, approve_request, reject_request, is_user_verified, get_user_requests

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

main_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "🤑 Заработать"],
    ["💰 Баланс", "📤 Пригласить"],
    ["📋 Инструкция", "📢 Рекламировать"],
    ["📞 Поддержка"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "📋 Список пользователей"],
    ["⚖️ Изменить баланс", "📋 Активные задания"],
    ["📢 Рассылка", "⛔ Забанить / Разбанить"],
    ["📤 Экспорт в файл", "⚙️ Настроить бонус"],
    ["📜 Журнал событий", "🔙 Выйти из админки"]
], resize_keyboard=True)

async def get_task_counts():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        channels = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE type = 'channel' AND active = 1")
        groups = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE type = 'group' AND active = 1")
        views = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE type = 'view' AND active = 1")
        bots = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE type = 'bot' AND active = 1")
        boosts = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE type = 'boost' AND active = 1")
        reactions = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE type = 'reaction' AND active = 1")
    except:
        channels = groups = views = bots = boosts = reactions = 0
    finally:
        await conn.close()
    return {
        "channels": channels or 0,
        "groups": groups or 0,
        "views": views or 0,
        "bots": bots or 0,
        "boosts": boosts or 0,
        "reactions": reactions or 0
    }

async def check_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        if await get_maintenance_mode():
            msg = await get_maintenance_message()
            await update.message.reply_text(msg)
            return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update, context):
        return

    user = update.effective_user
    user_id = user.id
    username = user.username or "Нет username"
    first_name = user.first_name or "Пользователь"

    # ===== РЕФЕРАЛЬНАЯ СИСТЕМА =====
    args = context.args
    referrer_id = None
    is_referral = False

    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].replace("ref_", ""))
            is_referral = True
        except:
            pass

    # Регистрируем пользователя (если ещё не зарегистрирован)
    await register_user(user_id, username, first_name)

    # Если это переход по ссылке и пригласивший существует
    if is_referral and referrer_id and referrer_id != user_id:
        # Проверяем, не забанен ли пригласивший
        if not await is_banned(referrer_id):
            # Начисляем бонус пригласившему (+500)
            await add_balance(referrer_id, 500)
            await add_log(referrer_id, "Получил реферальный бонус", f"За пользователя {user_id}")
            # Начисляем бонус новому пользователю (+500)
            await add_balance(user_id, 500)
            await add_log(user_id, "Получил реферальный бонус", f"От {referrer_id}")
            # Уведомляем пригласившего (если бот может написать ему)
            try:
                await context.bot.send_message(
                    referrer_id,
                    f"🎉 По твоей ссылке зарегистрировался новый пользователь!\n"
                    f"Ты и он получили по +500 COINS!"
                )
            except:
                pass
            await update.message.reply_text(
                f"🎉 Ты перешёл по приглашению!\n"
                f"Тебе и пригласившему начислено по +500 COINS!"
            )

    # Проверка на бан
    if await is_banned(user_id):
        await update.message.reply_text("⛔ Вы заблокированы.")
        return

    # Ежедневный бонус
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = await get_user(user_id)
    last_bonus = user_data['last_bonus'] if user_data else None
    bonus = await get_bonus_amount()

    if last_bonus != today:
        await add_balance(user_id, bonus)
        await conn.execute("UPDATE users SET last_bonus = $1 WHERE user_id = $2", today, user_id)
        await conn.close()
        balance = await get_balance(user_id)
        await update.message.reply_text(
            f"🎁 **Ежедневный бонус получен!**\n➕ {bonus} COINS зачислено на баланс.\n💰 Баланс: {balance}",
            parse_mode='Markdown',
            reply_markup=main_keyboard if user_id != ADMIN_ID else admin_keyboard
        )
    else:
        await update.message.reply_text(
            f"🏰 Добро пожаловать в **CoinFlow**!\n💰 Твой баланс: {await get_balance(user_id)} COINS",
            parse_mode='Markdown',
            reply_markup=main_keyboard if user_id != ADMIN_ID else admin_keyboard
        )

async def my_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = await get_balance(user_id)
    verified = await is_user_verified(user_id)
    badge = " ✅ (Верифицирован)" if verified else ""
    await update.message.reply_text(
        f"📊 Мой кабинет{badge}\n🆔 ID: {user_id}\n💰 Баланс: {balance} COINS",
        parse_mode='Markdown'
    )

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counts = await get_task_counts()
    text = (
        f"📊 **Статистика CoinFlow**\n\n"
        f"📢 Заданий на каналы: {counts['channels']}\n"
        f"👥 Заданий на группы: {counts['groups']}\n"
        f"👁️ Заданий на просмотр: {counts['views']}\n"
        f"🤖 Заданий на боты: {counts['bots']}\n"
        f"⚡ Заданий на бусты: {counts['boosts']}\n"
        f"🔥 Заданий на реакции: {counts['reactions']}\n\n"
        f"👑 Выберите способ заработка 👇"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 **Инструкция по использованию CoinFlow**\n\n"
        "💰 **Как зарабатывать COINS:**\n"
        "1️⃣ Нажми кнопку **«🤑 Заработать»**.\n"
        "2️⃣ Выбери тип задания (канал, группа, просмотр и т.д.).\n"
        "3️⃣ Нажми на задание и выполни условие (подпишись, вступи, поставь реакцию).\n"
        "4️⃣ Нажми **«✅ Проверить»** — бот автоматически проверит выполнение и начислит COINS.\n\n"
        "📌 **Важно:** Использование ботов и скриптов запрещено. Нарушение ведёт к блокировке."
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Подписаться на канал", callback_data="tasks_channels")],
        [InlineKeyboardButton("👥 Вступить в группу", callback_data="tasks_groups")],
        [InlineKeyboardButton("👁️ Просмотр постов", callback_data="tasks_views")],
        [InlineKeyboardButton("🤖 Перейти в бота", callback_data="tasks_bots")],
        [InlineKeyboardButton("⚡ Премиум буст (заряды)", callback_data="tasks_boosts")],
        [InlineKeyboardButton("🔥 Поставить реакции", callback_data="tasks_reactions")],
        [InlineKeyboardButton("🔙 В меню", callback_data="back_main")]
    ])
    await update.message.reply_text(
        "🤑 **Выберите способ заработка 👇**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def task_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_main":
        await start(update, context)
        return
    
    task_type_map = {
        "tasks_channels": "channel",
        "tasks_groups": "group",
        "tasks_views": "view",
        "tasks_bots": "bot",
        "tasks_boosts": "boost",
        "tasks_reactions": "reaction"
    }
    task_type = task_type_map.get(data)
    
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    tasks = await conn.fetch("SELECT id, name, link, reward FROM tasks WHERE type = $1 AND active = 1", task_type)
    await conn.close()
    
    if not tasks:
        await query.edit_message_text(
            f"📭 В этой категории пока нет заданий.\n\nЗайди позже! 🚀",
            parse_mode='Markdown'
        )
        return
    
    keyboard = []
    for task in tasks:
        keyboard.append([InlineKeyboardButton(
            f"🔹 {task['name']} ({task['reward']} COINS)",
            callback_data=f"do_{task['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    
    await query.edit_message_text(
        "🤑 **Доступные задания:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data == "back_main":
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
        except Exception as e:
            await query.edit_message_text("❌ Ошибка проверки. Убедись, что канал публичный.")
            return

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 **Поддержка CoinFlow**\n\n"
        "Если у тебя есть вопросы, проблемы или предложения, свяжись с администратором:\n"
        "👑 **@ArchibaldNn**\n\n"
        "💬 Также ты можешь зайти в наш чат:\n"
        "👉 @PrsAdvertisementMy",
        parse_mode='Markdown'
    )

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    await update.message.reply_text(
        f"📤 **Пригласи друга и получи бонус!**\n\n"
        f"Твоя уникальная ссылка:\n`{ref_link}`\n\n"
        f"🔥 Если кто-то перейдёт по твоей ссылке и зарегистрируется, **оба получат +500 COINS**!",
        parse_mode='Markdown'
    )

async def advertise_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Канал", callback_data="adv_channel")],
        [InlineKeyboardButton("👥 Группу", callback_data="adv_group")],
        [InlineKeyboardButton("👁️ Пост", callback_data="adv_post")],
        [InlineKeyboardButton("🤖 Бот", callback_data="adv_bot")],
        [InlineKeyboardButton("⚡ Премиум буст (заряды)", callback_data="adv_boost")],
        [InlineKeyboardButton("🔥 Реакции", callback_data="adv_reaction")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adv_back")]
    ])
    await update.message.reply_text(
        f"📢 **Что вы хотите рекламировать?**\n\n💰 Баланс: {await get_balance(update.effective_user.id)} COINS",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def advertise_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "adv_back":
        await start(update, context)
        return
    
    type_map = {
        "adv_channel": "channel",
        "adv_group": "group",
        "adv_post": "view",
        "adv_bot": "bot",
        "adv_boost": "boost",
        "adv_reaction": "reaction"
    }
    adv_type = type_map.get(data, "channel")
    context.user_data['adv_type'] = adv_type
    
    await query.edit_message_text(
        f"📢 **Выберите канал для рекламы**\n\n"
        f"1️⃣ Перешлите любое сообщение из канала в этот чат.\n"
        f"2️⃣ Убедитесь, что бот добавлен в этот канал.\n"
        f"3️⃣ Я автоматически создам задание для пользователей!\n\n"
        f"📌 *Если бот не добавлен — добавьте его и повторите.*",
        parse_mode='Markdown'
    )
    context.user_data['advertise_mode'] = True

async def handle_advertise_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('advertise_mode'):
        forwarded_msg = update.message.forward_from_chat
        
        if not forwarded_msg:
            await update.message.reply_text(
                "❌ Пожалуйста, **перешлите** сообщение из канала, который хотите рекламировать."
            )
            return
        
        chat_id = forwarded_msg.id
        chat_title = forwarded_msg.title or "Канал"
        
        try:
            chat_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                await update.message.reply_text(
                    f"❌ Бот не добавлен в канал **{chat_title}**.\n\n"
                    f"Добавьте бота в канал, затем перешлите сообщение ещё раз."
                )
                return
        except:
            await update.message.reply_text("❌ Не удалось проверить канал. Убедитесь, что бот добавлен.")
            return
        
        adv_type = context.user_data.get('adv_type', 'channel')
        reward = 200
        
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        await conn.execute(
            "INSERT INTO tasks (name, link, channel_id, type, reward) VALUES ($1, $2, $3, $4, $5)",
            f"Подпишись на {chat_title}", f"https://t.me/{chat_title}", chat_id, adv_type, reward
        )
        await conn.close()
        
        await update.message.reply_text(
            f"✅ **Задание создано!**\n\n"
            f"📢 Канал: {chat_title}\n"
            f"💰 Награда: {reward} COINS\n"
            f"📋 Тип: {adv_type}\n\n"
            f"Пользователи могут выполнить это задание в разделе «Заработать»."
        )
        context.user_data['advertise_mode'] = False
        context.user_data['adv_type'] = None

async def adminka_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа")
        return
    await admin_panel(update, context)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа")
        return
    await update.message.reply_text("👑 Панель управления CoinFlow", reply_markup=admin_keyboard)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users, total_coins, tasks_done = await get_stats()
    await update.message.reply_text(
        f"📊 Статистика\n👥 Пользователей: {total_users}\n💰 Всего COINS: {total_coins}\n✅ Выполнено заданий: {tasks_done}"
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = await get_all_users()
    text = "📋 Список пользователей:\n\n"
    for u in users:
        text += f"ID: {u['user_id']} | @{u['username']} | {u['first_name']} | {u['balance']} COINS\n"
    await update.message.reply_text(text[:4000])

async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⚖️ Введи ID и сумму через пробел:\nПример: 123456789 500")
    context.user_data['balance_mode'] = True

async def admin_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Канал", callback_data="add_type_channel")],
        [InlineKeyboardButton("👥 Группа", callback_data="add_type_group")],
        [InlineKeyboardButton("👁️ Просмотр", callback_data="add_type_view")],
        [InlineKeyboardButton("🤖 Бот", callback_data="add_type_bot")],
        [InlineKeyboardButton("⚡ Буст", callback_data="add_type_boost")],
        [InlineKeyboardButton("🔥 Реакция", callback_data="add_type_reaction")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ])
    await update.message.reply_text(
        "📝 **Выбери тип задания:**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def admin_add_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    data = query.data
    
    if data == "admin_back":
        await admin_panel(update, context)
        return
    
    if data.startswith("add_type_"):
        task_type = data.replace("add_type_", "")
        context.user_data['adding_task_type'] = task_type
        await query.edit_message_text(
            f"📝 **Добавление задания**\n\n"
            f"Тип: `{task_type}`\n\n"
            f"Введи данные в формате:\n"
            f"`Название | Ссылка | Награда`\n\n"
            f"Пример:\n"
            f"`Мой канал | https://t.me/MyChannel | 500`",
            parse_mode='Markdown'
        )
        context.user_data['task_add_mode'] = True

async def handle_admin_task_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('task_add_mode') and update.effective_user.id == ADMIN_ID:
        text = update.message.text
        parts = text.split("|")
        if len(parts) != 3:
            await update.message.reply_text("❌ Неверный формат! Используй: Название | Ссылка | Награда")
            return
        name = parts[0].strip()
        link = parts[1].strip()
        try:
            reward = int(parts[2].strip())
        except:
            await update.message.reply_text("❌ Награда должна быть числом!")
            return
        
        task_type = context.user_data.get('adding_task_type', 'channel')
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        await conn.execute(
            "INSERT INTO tasks (name, link, channel_id, type, reward) VALUES ($1, $2, $3, $4, $5)",
            name, link, link, task_type, reward
        )
        await conn.close()
        
        context.user_data['task_add_mode'] = False
        context.user_data['adding_task_type'] = None
        
        await update.message.reply_text(f"✅ Задание '{name}' добавлено! Тип: {task_type}")
        return
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("📢 Введи текст для рассылки всем пользователям:")
    context.user_data['broadcast_mode'] = True

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⛔ Введи ID пользователя для бана / разбана:\nИспользуй формат: ID ban или ID unban\nПример: 123456789 ban")
    context.user_data['ban_mode'] = True

async def admin_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⚙️ Введи новую сумму ежедневного бонуса:\n(Например: 3000)")
    context.user_data['bonus_mode'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update, context):
        return
    text = update.message.text
    user_id = update.effective_user.id

    if text == "📊 Статистика":
        await bot_stats(update, context)
    elif text == "🤑 Заработать":
        await earn(update, context)
    elif text == "💰 Баланс":
        await my_cabinet(update, context)
    elif text == "📤 Пригласить":
        await invite(update, context)
    elif text == "📋 Инструкция":
        await instructions(update, context)
    elif text == "📢 Рекламировать":
        await advertise_menu(update, context)
    elif text == "📞 Поддержка":
        await support(update, context)
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
        elif text == "⚙️ Настроить бонус":
            await admin_bonus(update, context)
        elif text == "🔙 Выйти из админки":
            await update.message.reply_text("👋 Выход из админки.", reply_markup=main_keyboard)
        else:
            await update.message.reply_text("⏳ В разработке")
    elif context.user_data.get('task_add_mode') and user_id == ADMIN_ID:
        await handle_admin_task_input(update, context)
        return
    elif context.user_data.get('advertise_mode'):
        await handle_advertise_request(update, context)
        return
    elif context.user_data.get('balance_mode') and user_id == ADMIN_ID:
        try:
            parts = text.split()
            target_id = int(parts[0])
            amount = int(parts[1])
            await add_balance(target_id, amount)
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
        await update.message.reply_text(f"✅ Рассылка отправлена! {sent} человек.")
        context.user_data['broadcast_mode'] = False
    elif context.user_data.get('ban_mode') and user_id == ADMIN_ID:
        try:
            parts = text.split()
            target_id = int(parts[0])
            action = parts[1].lower()
            if action == "ban":
                await set_ban(target_id, True)
                await update.message.reply_text(f"⛔ Пользователь {target_id} забанен.")
            elif action == "unban":
                await set_ban(target_id, False)
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
            await update.message.reply_text(f"✅ Бонус изменён на {new_bonus} COINS")
        except:
            await update.message.reply_text("❌ Введи число!")
        context.user_data['bonus_mode'] = False
    else:
        await update.message.reply_text("⏳ В разработке")

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

async def main():
    await init_db()
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adminka", adminka_command))

    application.add_handler(CallbackQueryHandler(task_category_handler, pattern="^(tasks_|back_main)"))
    application.add_handler(CallbackQueryHandler(task_handler, pattern="^(do_|back_main)"))
    application.add_handler(CallbackQueryHandler(admin_add_task_callback, pattern="^(add_type_|admin_back)"))
    application.add_handler(CallbackQueryHandler(advertise_handler, pattern="^(adv_|back_)"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 CoinFlow с реферальной системой запущен!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await start_web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
