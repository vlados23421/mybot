import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# Импорты из новой базы данных PostgreSQL
from database import init_db, get_user, register_user, update_bonus, get_stats, is_task_done, mark_task_done, add_balance, get_all_tasks, get_task, add_task, delete_task

# ==========================================
# НАСТРОЙКИ
# ==========================================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ==========================================
# КНОПКИ (КЛАВИАТУРА)
# ==========================================
main_keyboard = ReplyKeyboardMarkup([
    ["🤑 Заработать", "📊 Мой кабинет"],
    ["📢 Рекламировать", "🧾 Чеки"],
    ["📎 Полезные ссылки", "🤖 Наши боты"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["📊 Статистика", "📢 Рассылка"],
    ["💰 Выдать монеты", "📝 Управление заданиями"],
    ["🔙 Выйти из админки"]
], resize_keyboard=True)

# ==========================================
# ФУНКЦИИ БОТА
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = await get_user(user.id)
    last_bonus = user_data[4]
    
    if last_bonus != today:
        await update_bonus(user.id, today)
        user_data = await get_user(user.id)
        text = f"🎉 Вам начислен бонус 2500 COINS!\n💰 Баланс: {user_data[3]} COINS"
    else:
        text = f"🏰 Добро пожаловать в PIAR BOT!\n💰 Твой баланс: {user_data[3]} COINS"
    
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(text, reply_markup=admin_keyboard)
    else:
        await update.message.reply_text(text, reply_markup=main_keyboard)

async def my_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if user:
        balance = user[3]
        await update.message.reply_text(
            f"📊 Мой кабинет\n"
            f"🆔 ID: {user[0]}\n"
            f"👤 Имя: {user[2]}\n"
            f"💰 Баланс: {balance} COINS"
        )

async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = await get_all_tasks(only_active=True)
    keyboard = []
    
    if not tasks:
        await update.message.reply_text("📭 Сейчас нет активных заданий. Зайди позже!")
        return
    
    for task in tasks:
        task_id, name, link, reward = task
        done = await is_task_done(user_id, task_id)
        if done:
            status = "✅ (Выполнено)"
        else:
            status = f"🔹 Получить {reward} COINS"
        
        keyboard.append([InlineKeyboardButton(
            f"{name} - {status}",
            callback_data=f"do_task_{task_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤑 Выбери задание:",
        reply_markup=reply_markup
    )

async def task_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # --- ОБРАБОТКА АДМИНСКИХ КНОПОК ЗАДАНИЙ ---
    if data == "admin_add_task":
        await admin_add_task_callback(update, context)
        return
    if data == "admin_del_task":
        await admin_del_task_callback(update, context)
        return
    if data.startswith("del_task_"):
        await admin_del_confirm(update, context)
        return
    if data == "admin_back":
        await admin_back(update, context)
        return
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---
    
    if data == "back_to_menu":
        await start(update, context)
        return
    
    if data.startswith("do_task_"):
        task_id = int(data.replace("do_task_", ""))
        user_id = update.effective_user.id
        
        if await is_task_done(user_id, task_id):
            await query.edit_message_text("✅ Ты уже выполнил это задание!")
            return
        
        task = await get_task(task_id)
        if not task:
            await query.edit_message_text("❌ Задание не найдено!")
            return
        
        name, link, reward = task[1], task[2], task[3]
        
        await query.edit_message_text(
            f"🔗 Перейди по ссылке:\n{link}\n\n"
            f"После выполнения нажми кнопку ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я выполнил!", callback_data=f"done_{task_id}")]
            ])
        )
    
    if data.startswith("done_"):
        task_id = int(data.replace("done_", ""))
        user_id = update.effective_user.id
        
        if await is_task_done(user_id, task_id):
            await query.edit_message_text("✅ Ты уже получил награду!")
            return
        
        task = await get_task(task_id)
        if not task:
            await query.edit_message_text("❌ Ошибка!")
            return
        
        reward = task[3]
        await add_balance(user_id, reward)
        await mark_task_done(user_id, task_id)
        
        await query.edit_message_text(
            f"🎉 Поздравляем! Ты получил {reward} COINS!\n"
            f"💰 Новый баланс: {(await get_user(user_id))[3]} COINS"
                                       )
    
    if data.startswith("done_"):
        task_id = int(data.replace("done_", ""))
        user_id = update.effective_user.id
        
        if await is_task_done(user_id, task_id):
            await query.edit_message_text("✅ Ты уже получил награду!")
            return
        
        task = await get_task(task_id)
        if not task:
            await query.edit_message_text("❌ Ошибка!")
            return
        
        reward = task[3]
        await add_balance(user_id, reward)
        await mark_task_done(user_id, task_id)
        
        await query.edit_message_text(
            f"🎉 Поздравляем! Ты получил {reward} COINS!\n"
            f"💰 Новый баланс: {(await get_user(user_id))[3]} COINS"
        )

# ==========================================
# НОВАЯ АДМИНКА (ПАНЕЛЬ УПРАВЛЕНИЯ)
# ==========================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет доступа к админке!")
        return
    
    await update.message.reply_text(
        "👑 Добро пожаловать в Админ-панель!\n"
        "Выбери действие:",
        reply_markup=admin_keyboard
    )

async def adminka_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users, total_coins = await get_stats()
    await update.message.reply_text(
        f"📊 Статистика проекта:\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"💰 Всего COINS: {total_coins}\n"
        f"🆔 Твой ID: {update.effective_user.id}"
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "📢 Введи текст для рассылки:\n\n"
        "Напиши сообщение, которое получит КАЖДЫЙ пользователь бота."
    )
    context.user_data['broadcast_mode'] = True

async def admin_give_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "💰 Введи ID пользователя и сумму через пробел:\n\n"
        "Пример: 8915047087 500\n"
        "(Выдаст 500 COINS пользователю с этим ID)"
    )
    context.user_data['give_mode'] = True

async def admin_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    tasks = await get_all_tasks(only_active=True)
    text = "📝 Список активных заданий:\n\n"
    for task in tasks:
        text += f"ID: {task[0]} | {task[1]} | Награда: {task[3]} COINS\n"
    if not tasks:
        text += "(Заданий пока нет)\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить задание", callback_data="admin_add_task")],
        [InlineKeyboardButton("❌ Удалить задание", callback_data="admin_del_task")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def admin_add_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    await query.edit_message_text(
        "📝 Введи данные нового задания в формате:\n\n"
        "<code>Название | Ссылка | Награда</code>\n\n"
        "Пример:\n"
        "Подпишись на канал | https://t.me/Channel | 500"
    )
    context.user_data['task_add_mode'] = True

async def admin_del_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    
    tasks = await get_all_tasks(only_active=False)
    kb = []
    for task in tasks:
        kb.append([InlineKeyboardButton(
            f"Удалить: {task[1]} ({task[3]} COINS)",
            callback_data=f"del_task_{task[0]}"
        )])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    await query.edit_message_text(
        "Выбери задание для удаления:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def admin_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    task_id = int(query.data.replace("del_task_", ""))
    await delete_task(task_id)
    await query.edit_message_text(f"✅ Задание ID {task_id} удалено!")

async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    await admin_tasks(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    # --- ОБРАБОТКА АДМИНСКИХ КНОПОК ---
    if text == "📊 Статистика":
        await admin_stats(update, context)
        return
    if text == "📢 Рассылка":
        await admin_broadcast(update, context)
        return
    if text == "💰 Выдать монеты":
        await admin_give_coins(update, context)
        return
    if text == "📝 Управление заданиями":
        await admin_tasks(update, context)
        return
    if text == "🔙 Выйти из админки":
        await update.message.reply_text("👋 Вы вышли из админки.", reply_markup=main_keyboard)
        return
    
    # --- ОБРАБОТКА ВВОДА ТЕКСТА ---
    if context.user_data.get('broadcast_mode') and user_id == ADMIN_ID:
        conn = None
        context.user_data['broadcast_mode'] = False
        await update.message.reply_text("⏳ Функция рассылки требует доработки для PostgreSQL. Реализую позже.")
        return
    
    if context.user_data.get('task_add_mode') and user_id == ADMIN_ID:
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
        await add_task(name, link, reward)
        context.user_data['task_add_mode'] = False
        await update.message.reply_text(f"✅ Задание '{name}' успешно добавлено! Награда: {reward} COINS")
        return
    
    if context.user_data.get('give_mode') and user_id == ADMIN_ID:
        try:
            parts = text.split()
            target_id = int(parts[0])
            amount = int(parts[1])
            await add_balance(target_id, amount)
            context.user_data['give_mode'] = False
            await update.message.reply_text(f"✅ Пользователю {target_id} выдано {amount} COINS!")
        except:
            await update.message.reply_text("❌ Ошибка! Введи в формате: ID Сумма")
        return
    
    # --- ОБЫЧНЫЕ КНОПКИ ---
    if text == "📊 Мой кабинет":
        await my_cabinet(update, context)
    elif text == "🤑 Заработать":
        await earn(update, context)
    elif text == "📢 Рекламировать":
        await update.message.reply_text("📢 Свяжитесь с администратором для заказа рекламы.")
    elif text == "🧾 Чеки":
        await update.message.reply_text("⏳ Функция 'Чеки' в разработке.")
    elif text == "📎 Полезные ссылки":
        await update.message.reply_text("🔗 Наш канал: @CoinFlowNews")
    elif text == "🤖 Наши боты":
        await update.message.reply_text("🤖 Функция находится в разработке")
    else:
        await update.message.reply_text("⏳ Эта функция находится в разработке! Скоро она заработает.")

# ==========================================
# ЗАПУСК БОТА И ВЕБ-СЕРВЕРА
# ==========================================
import aiohttp
from aiohttp import web

async def health_check(request):
    return web.Response(text="OK")

async def main():
    # ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (ВАЖНО: теперь с await)
    await init_db()
    
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adminka", adminka_command))
    application.add_handler(CallbackQueryHandler(task_button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 PIAR BOT (PostgreSQL) запущен! Всё готово к работе.")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    port = int(os.environ.get('PORT', 8080))
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Веб-сервер запущен на порту {port}")

    try:
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
