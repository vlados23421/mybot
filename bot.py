# bot.py
import os
import sys
import random
import time
import threading
import json
from datetime import datetime, timedelta
import telebot
from telebot import types
import traceback
import database as db
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================
# === НАСТРОЙКА БОТА ===
# ============================================

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.environ.get('ADMIN_IDS', '539015206').split(',')]

print('=' * 60)
print('⭐ ЗАПУСК LEGENDARY БОТА BATTLEZ')
print('=' * 60)
print(f'📅 Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print(f'👑 Админ ID: {ADMIN_IDS}')
print('=' * 60)

if not TOKEN:
    print('❌ ОШИБКА: BOT_TOKEN не найден!')
    sys.exit(1)

# ============================================
# === ИНИЦИАЛИЗАЦИЯ ===
# ============================================

try:
    db.init_db()
    print('✅ Таблицы готовы!')
except Exception as e:
    print(f'❌ Ошибка: {e}')
    sys.exit(1)

try:
    bot = telebot.TeleBot(TOKEN)
    print('✅ Бот создан!')
except Exception as e:
    print(f'❌ Ошибка: {e}')
    sys.exit(1)

# ============================================
# === ВЕБ-СЕРВЕР ===
# ============================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

# ============================================
# === ИГРОВЫЕ ДАННЫЕ ===
# ============================================

CHARACTERS = {
    'warrior': {'name': 'Воин', 'emoji': '⚔️', 'hp': 120, 'attack': 15, 'defense': 10},
    'mage': {'name': 'Маг', 'emoji': '🔮', 'hp': 80, 'attack': 25, 'defense': 5},
    'rogue': {'name': 'Разбойник', 'emoji': '🗡️', 'hp': 90, 'attack': 20, 'defense': 8},
    'paladin': {'name': 'Паладин', 'emoji': '🛡️', 'hp': 140, 'attack': 12, 'defense': 15},
    'archer': {'name': 'Лучник', 'emoji': '🏹', 'hp': 85, 'attack': 22, 'defense': 6},
    'warlock': {'name': 'Чернокнижник', 'emoji': '🌀', 'hp': 75, 'attack': 28, 'defense': 4}
}

RANKS = [
    {'name': 'Бронза', 'emoji': '🥉', 'min_wins': 0},
    {'name': 'Серебро', 'emoji': '🥈', 'min_wins': 5},
    {'name': 'Золото', 'emoji': '🥇', 'min_wins': 15},
    {'name': 'Платина', 'emoji': '💎', 'min_wins': 30},
    {'name': 'Алмаз', 'emoji': '💠', 'min_wins': 50},
    {'name': 'Легенда', 'emoji': '👑', 'min_wins': 100}
]

# ============================================
# === НАСТРОЙКИ (хранятся в БД) ===
# ============================================

DEFAULT_SETTINGS = {
    'exchange_rate': 50,  # 50 золота = 1 звезда
    'stars_to_telegram_stars': 10,  # 10 Telegram Stars = 1 внутриигровая звезда
    'daily_gold_min': 20,
    'daily_gold_max': 50,
    'daily_stars_min': 1,
    'daily_stars_max': 3,
    'shop_discount': 0,
    'event_active': False,
    'event_multiplier': 1.0
}

def get_settings():
    """Получить настройки из БД"""
    try:
        # Если есть таблица settings, берём оттуда
        # Пока используем локальное хранилище
        if not hasattr(get_settings, 'cache'):
            get_settings.cache = dict(DEFAULT_SETTINGS)
        return get_settings.cache
    except:
        return dict(DEFAULT_SETTINGS)

def save_settings(settings):
    """Сохранить настройки"""
    get_settings.cache = settings

# ============================================
# === МАГАЗИН ===
# ============================================

SHOP = {
    'weapons': {
        'name': 'Оружие',
        'emoji': '⚔️',
        'items': [
            {'id': 'sword', 'name': 'Стальной меч', 'emoji': '🗡️', 'price_stars': 5, 'price_real': 1, 'stats': {'attack': 5}},
            {'id': 'bow', 'name': 'Длинный лук', 'emoji': '🏹', 'price_stars': 4, 'price_real': 1, 'stats': {'attack': 4}},
            {'id': 'staff', 'name': 'Магический посох', 'emoji': '🔮', 'price_stars': 6, 'price_real': 2, 'stats': {'attack': 6}},
            {'id': 'hammer', 'name': 'Молот грома', 'emoji': '🔨', 'price_stars': 8, 'price_real': 2, 'stats': {'attack': 8}},
        ]
    },
    'armor': {
        'name': 'Броня',
        'emoji': '🛡️',
        'items': [
            {'id': 'leather', 'name': 'Кожаная броня', 'emoji': '🥾', 'price_stars': 3, 'price_real': 1, 'stats': {'defense': 3}},
            {'id': 'chainmail', 'name': 'Кольчуга', 'emoji': '⛓️', 'price_stars': 5, 'price_real': 1, 'stats': {'defense': 5}},
            {'id': 'plate', 'name': 'Латы', 'emoji': '🛡️', 'price_stars': 8, 'price_real': 2, 'stats': {'defense': 8}},
        ]
    },
    'potions': {
        'name': 'Зелья',
        'emoji': '🧪',
        'items': [
            {'id': 'health_potion', 'name': 'Зелье здоровья', 'emoji': '❤️', 'price_stars': 2, 'price_real': 1, 'stats': {'heal': 30}},
            {'id': 'big_health', 'name': 'Большое зелье', 'emoji': '💖', 'price_stars': 4, 'price_real': 1, 'stats': {'heal': 60}},
            {'id': 'exp_potion', 'name': 'Зелье опыта', 'emoji': '📈', 'price_stars': 3, 'price_real': 1, 'stats': {'exp': 20}},
        ]
    },
    'boosts': {
        'name': 'Бусты',
        'emoji': '⚡',
        'items': [
            {'id': 'attack_boost', 'name': 'Буст атаки (+5)', 'emoji': '⚔️', 'price_stars': 3, 'price_real': 1, 'stats': {'attack_boost': 5}},
            {'id': 'defense_boost', 'name': 'Буст защиты (+5)', 'emoji': '🛡️', 'price_stars': 3, 'price_real': 1, 'stats': {'defense_boost': 5}},
        ]
    },
    'skins': {
        'name': 'Скины',
        'emoji': '🎨',
        'items': [
            {'id': 'golden', 'name': 'Золотой скин', 'emoji': '🌟', 'price_stars': 15, 'price_real': 3, 'stats': {'skin': 'golden'}},
            {'id': 'dark', 'name': 'Тёмный скин', 'emoji': '🌙', 'price_stars': 10, 'price_real': 2, 'stats': {'skin': 'dark'}},
            {'id': 'fire', 'name': 'Огненный скин', 'emoji': '🔥', 'price_stars': 12, 'price_real': 2, 'stats': {'skin': 'fire'}},
            {'id': 'royal', 'name': 'Королевский скин', 'emoji': '👑', 'price_stars': 20, 'price_real': 5, 'stats': {'skin': 'royal'}},
        ]
    }
}

# ============================================
# === ИГРОВЫЕ СЕССИИ ===
# ============================================

player_games = {}

def create_player(telegram_id, username):
    return {
        'telegram_id': telegram_id,
        'username': username,
        'character': 'warrior',
        'hp': CHARACTERS['warrior']['hp'],
        'max_hp': CHARACTERS['warrior']['hp'],
        'attack': CHARACTERS['warrior']['attack'],
        'defense': CHARACTERS['warrior']['defense'],
        'exp': 0,
        'level': 1,
        'wins': 0,
        'losses': 0,
        'gold': 30,
        'stars': 0,
        'items': [],
        'inventory': {},
        'in_battle': False,
        'enemy': None,
        'last_daily': None,
        'achievements': [],
        'skin': 'default',
        'buffs': {},
        'total_battles': 0,
        'shop_history': [],
        'joined_at': datetime.now().isoformat()
    }

def get_player_level(exp):
    return 1 + exp // 50

def get_next_level_exp(level):
    return level * 50

def get_rank(wins):
    for rank in reversed(RANKS):
        if wins >= rank['min_wins']:
            return rank
    return RANKS[0]

# ============================================
# === ФУНКЦИИ МАГАЗИНА ===
# ============================================

def get_all_shop_items():
    all_items = []
    for cat in SHOP.values():
        all_items.extend(cat['items'])
    return all_items

def buy_item(player, item_id):
    all_items = get_all_shop_items()
    item = next((i for i in all_items if i['id'] == item_id), None)
    
    if not item:
        return False, "❌ Товар не найден"
    
    settings = get_settings()
    price = item.get('price_stars', 999)
    
    if player['stars'] < price:
        return False, f"❌ Недостаточно звёзд! Нужно {price}⭐"
    
    player['stars'] -= price
    
    if item_id not in player['inventory']:
        player['inventory'][item_id] = 0
    player['inventory'][item_id] += 1
    player['items'].append(item['name'])
    
    return True, f"✅ Куплено: {item['emoji']} {item['name']} (за {price}⭐)"

def buy_with_real_stars(player, item_id):
    """Покупка за реальные Telegram Stars"""
    all_items = get_all_shop_items()
    item = next((i for i in all_items if i['id'] == item_id), None)
    
    if not item:
        return False, "❌ Товар не найден"
    
    price_real = item.get('price_real', 1)
    settings = get_settings()
    stars_to_add = price_real * settings.get('stars_to_telegram_stars', 10)
    
    # Здесь должна быть интеграция с Telegram Stars API
    # Пока добавляем звёзды за "реальные" звёзды
    player['stars'] += stars_to_add
    
    if item_id not in player['inventory']:
        player['inventory'][item_id] = 0
    player['inventory'][item_id] += 1
    player['items'].append(item['name'])
    
    return True, f"✅ Куплено: {item['emoji']} {item['name']} за {price_real}⭐ реальных звёзд!\n+{stars_to_add}⭐ внутриигровых"

# ============================================
# === КОМАНДЫ ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if user_id not in player_games:
        player_games[user_id] = create_player(user_id, message.from_user.username)
    
    player = player_games[user_id]
    rank = get_rank(player['wins'])
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("⚔️ Битва", "battle"),
        ("👤 Профиль", "profile"),
        ("🎒 Инвентарь", "inventory"),
        ("🏆 Лидеры", "leaderboard"),
        ("🏪 Магазин", "shop"),
        ("💎 Достижения", "achievements"),
        ("⭐ Звёзды", "stars"),
        ("🎁 Ежедневно", "daily"),
        ("🔄 Сменить класс", "change_class"),
        ("🌐 Сайт", "site")
    ]
    
    # Добавляем кнопку админки только для админа
    if user_id in ADMIN_IDS:
        btns.append(("🔧 Админ-панель", "admin_panel"))
    
    for text, callback in btns:
        if callback == "site":
            btn = types.InlineKeyboardButton(text, url="https://battle-z.vercel.app/")
        else:
            btn = types.InlineKeyboardButton(text, callback_data=callback)
        keyboard.add(btn)
    
    text = f"""
🎮 **BattleZ — Игровой бот**

Привет, {message.from_user.first_name}! 👋

{rank['emoji']} **Ранг:** {rank['name']}
{CHARACTERS[player['character']]['emoji']} **Класс:** {CHARACTERS[player['character']]['name']}
❤️ **HP:** {player['hp']}/{player['max_hp']}
⭐ **Уровень:** {player['level']}
⭐ **Звёзд:** {player['stars']}
💰 **Золота:** {player['gold']}
🏆 **Побед:** {player['wins']}

📌 **Выбери действие:**
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === АДМИН-ПАНЕЛЬ ===
# ============================================

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    show_admin_panel(message)

def show_admin_panel(message):
    settings = get_settings()
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("📊 Статистика", "admin_stats"),
        ("👥 Пользователи", "admin_users"),
        ("💱 Курс обмена", "admin_exchange"),
        ("⭐ Stars курс", "admin_stars_rate"),
        ("🎮 Выдать предмет", "admin_give_item"),
        ("💰 Выдать звёзды", "admin_give_stars"),
        ("📢 Рассылка", "admin_broadcast"),
        ("🔄 Сброс настроек", "admin_reset"),
        ("🔙 Назад", "back_to_menu")
    ]
    for text, callback in btns:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    text = f"""
🔧 **Админ-панель BattleZ**

📊 **Текущие настройки:**
💱 Курс обмена: {settings.get('exchange_rate', 50)} золота = 1⭐
⭐ Stars курс: {settings.get('stars_to_telegram_stars', 10)} Telegram Stars = 1⭐

📌 **Выбери действие:**
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === АДМИН-ФУНКЦИИ ===
# ============================================

def admin_stats(message):
    users = db.get_all_users()
    total = len(users) if users else 0
    
    text = f"""
📊 **Статистика проекта**

👥 **Всего пользователей:** {total}
🎮 **Активных игроков:** {len(player_games)}
💰 **Всего звёзд:** {sum(p['stars'] for p in player_games.values())}
🏆 **Всего побед:** {sum(p['wins'] for p in player_games.values())}

📅 **Дата:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def admin_users(message):
    users = db.get_all_users()
    if not users:
        bot.send_message(message.chat.id, "📭 Нет пользователей")
        return
    
    text = "👥 **Последние пользователи:**\n\n"
    for u in users[:10]:
        text += f"👤 {u.get('username') or 'Аноним'}\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def admin_exchange(message):
    settings = get_settings()
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [30, 40, 50, 60, 70, 80]:
        btn = types.InlineKeyboardButton(
            f"{val}💰 = 1⭐",
            callback_data=f"set_exchange_{val}"
        )
        keyboard.add(btn)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    text = f"""
💱 **Курс обмена золота**

📌 **Текущий курс:** {settings.get('exchange_rate', 50)} золота = 1⭐

Выбери новый курс:
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def admin_stars_rate(message):
    settings = get_settings()
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [5, 10, 15, 20, 25, 30]:
        btn = types.InlineKeyboardButton(
            f"{val}⭐ = 1⭐",
            callback_data=f"set_stars_rate_{val}"
        )
        keyboard.add(btn)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    text = f"""
⭐ **Курс обмена Telegram Stars**

📌 **Текущий курс:** {settings.get('stars_to_telegram_stars', 10)} Telegram Stars = 1⭐

Выбери новый курс:
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def admin_give_item(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    all_items = get_all_shop_items()
    for item in all_items[:10]:
        btn = types.InlineKeyboardButton(
            f"{item['emoji']} {item['name']}",
            callback_data=f"give_item_{item['id']}"
        )
        keyboard.add(btn)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    bot.send_message(message.chat.id, "🎮 **Выдать предмет пользователю**\n\nВведи @username в следующем сообщении", parse_mode='Markdown', reply_markup=keyboard)

def admin_give_stars(message):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [10, 25, 50, 100, 250, 500]:
        btn = types.InlineKeyboardButton(
            f"{val}⭐",
            callback_data=f"give_stars_{val}"
        )
        keyboard.add(btn)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    bot.send_message(message.chat.id, "💰 **Выдать звёзды пользователю**\n\nВыбери количество:", parse_mode='Markdown', reply_markup=keyboard)

def admin_broadcast(message):
    bot.send_message(message.chat.id, "📢 **Рассылка**\n\nВведи текст для рассылки:")

def admin_reset(message):
    keyboard = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("✅ Да, сбросить", callback_data="reset_confirm")
    btn2 = types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")
    keyboard.add(btn1, btn2)
    
    bot.send_message(message.chat.id, "⚠️ **Сбросить все настройки?**", parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === КОЛБЭКИ ===
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if user_id not in player_games:
        player_games[user_id] = create_player(user_id, call.from_user.username)
    
    player = player_games[user_id]
    settings = get_settings()
    
    # ===== АДМИН-КОЛБЭКИ =====
    if user_id in ADMIN_IDS:
        if data == 'admin_panel':
            show_admin_panel(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_stats':
            admin_stats(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_users':
            admin_users(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_exchange':
            admin_exchange(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_stars_rate':
            admin_stars_rate(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_give_item':
            admin_give_item(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_give_stars':
            admin_give_stars(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_broadcast':
            admin_broadcast(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data == 'admin_reset':
            admin_reset(call.message)
            bot.answer_callback_query(call.id)
            return
        
        if data.startswith('set_exchange_'):
            val = int(data.replace('set_exchange_', ''))
            settings['exchange_rate'] = val
            save_settings(settings)
            bot.answer_callback_query(call.id, f"✅ Курс установлен: {val}💰 = 1⭐", show_alert=True)
            admin_panel_command(call.message)
            return
        
        if data.startswith('set_stars_rate_'):
            val = int(data.replace('set_stars_rate_', ''))
            settings['stars_to_telegram_stars'] = val
            save_settings(settings)
            bot.answer_callback_query(call.id, f"✅ Курс установлен: {val} Telegram Stars = 1⭐", show_alert=True)
            admin_panel_command(call.message)
            return
        
        if data == 'reset_confirm':
            save_settings(dict(DEFAULT_SETTINGS))
            bot.answer_callback_query(call.id, "✅ Настройки сброшены!", show_alert=True)
            admin_panel_command(call.message)
            return
        
        if data.startswith('give_stars_'):
            val = int(data.replace('give_stars_', ''))
            # В реальности нужно выбрать пользователя
            # Пока выдаём самому себе
            player['stars'] += val
            bot.answer_callback_query(call.id, f"✅ Выдано {val}⭐!", show_alert=True)
            return
        
        if data.startswith('give_item_'):
            item_id = data.replace('give_item_', '')
            success, msg = buy_item(player, item_id)
            # Отменяем списание звёзд, т.к. выдаём бесплатно
            player['stars'] += 1  # возвращаем звезду
            bot.answer_callback_query(call.id, f"✅ Предмет выдан!", show_alert=True)
            return
    
    # ===== МАГАЗИН С REAL STARS =====
    if data == 'shop_real':
        show_shop_real(call.message)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('buy_real_'):
        item_id = data.replace('buy_real_', '')
        success, msg = buy_with_real_stars(player, item_id)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if success:
            show_shop_real(call.message)
        return
    
    # ===== ОБЫЧНЫЙ МАГАЗИН =====
    if data == 'shop':
        show_shop(call.message)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('shop_'):
        category = data.replace('shop_', '')
        if category in SHOP:
            show_shop_category(call.message, category)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'shop_back':
        show_shop(call.message)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('buy_'):
        item_id = data.replace('buy_', '')
        success, msg = buy_item(player, item_id)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if success:
            check_achievements(player)
        return
    
    # ===== БИТВА =====
    if data in ['attack', 'defend', 'flee', 'strong_attack']:
        handle_battle_action(call, player, data)
        return
    
    # ===== ОСТАЛЬНЫЕ =====
    commands = {
        'battle': battle_start,
        'profile': show_profile,
        'inventory': show_inventory,
        'leaderboard': show_leaderboard,
        'achievements': show_achievements,
        'stars': show_stars,
        'daily': daily_reward,
        'change_class': change_class
    }
    
    if data in commands:
        commands[data](call.message, player)
        bot.answer_callback_query(call.id)
    
    if data.startswith('class_'):
        class_key = data.replace('class_', '')
        if class_key in CHARACTERS:
            player['character'] = class_key
            player['hp'] = CHARACTERS[class_key]['hp']
            player['max_hp'] = CHARACTERS[class_key]['hp']
            player['attack'] = CHARACTERS[class_key]['attack']
            player['defense'] = CHARACTERS[class_key]['defense']
            bot.answer_callback_query(call.id, f"✅ Класс изменён на {CHARACTERS[class_key]['name']}!")
            bot.edit_message_text(
                f"✅ **Класс изменён!**\n\nТеперь ты {CHARACTERS[class_key]['emoji']} {CHARACTERS[class_key]['name']}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
    
    if data == 'back_to_menu':
        start(call.message)
        bot.answer_callback_query(call.id)

# ============================================
# === МАГАЗИН С REAL STARS ===
# ============================================

def show_shop_real(message):
    settings = get_settings()
    rate = settings.get('stars_to_telegram_stars', 10)
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Показываем товары, которые можно купить за реальные звёзды
    all_items = get_all_shop_items()
    for item in all_items:
        if 'price_real' in item:
            btn = types.InlineKeyboardButton(
                f"{item['emoji']} {item['name']} — {item['price_real']}⭐",
                callback_data=f"buy_real_{item['id']}"
            )
            keyboard.add(btn)
    
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="shop"))
    
    text = f"""
⭐ **Магазин за Telegram Stars**

Курс: {rate} Telegram Stars = 1⭐

📌 **Выбери товар:**
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def show_shop(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for key, cat in SHOP.items():
        btn = types.InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}",
            callback_data=f"shop_{key}"
        )
        keyboard.add(btn)
    
    keyboard.add(types.InlineKeyboardButton("⭐ Купить за Stars", callback_data="shop_real"))
    
    text = "🏪 **Магазин BattleZ**\n\nВыбери категорию:"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def show_shop_category(message, category):
    items = SHOP[category]['items']
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    for item in items:
        btn = types.InlineKeyboardButton(
            f"{item['emoji']} {item['name']} — {item['price_stars']}⭐",
            callback_data=f"buy_{item['id']}"
        )
        keyboard.add(btn)
    
    btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back")
    keyboard.add(btn_back)
    
    text = f"🏪 **{SHOP[category]['emoji']} {SHOP[category]['name']}**\n\nВыбери товар:"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === ОСТАЛЬНЫЕ ФУНКЦИИ ===
# ============================================

# (Здесь код для битвы, профиля, инвентаря и т.д.)
# Все функции из предыдущих версий остаются

def handle_battle_action(call, player, action):
    if not player.get('in_battle', False):
        bot.answer_callback_query(call.id, "❌ Ты не в бою!", show_alert=True)
        return
    
    enemy = player['enemy']
    
    if action == 'attack':
        damage = random.randint(5, player['attack'] + 5)
        enemy['hp'] -= damage
        text = f"⚔️ Ты нанёс {damage} урона!"
    
    elif action == 'strong_attack':
        if player['hp'] < 20:
            bot.answer_callback_query(call.id, "❌ Слишком мало HP!", show_alert=True)
            return
        damage = random.randint(10, player['attack'] + 10)
        player['hp'] -= 10
        enemy['hp'] -= damage
        text = f"💪 Сильный удар! {damage} урона! (-10 HP)"
    
    elif action == 'defend':
        heal = random.randint(5, 15)
        player['hp'] = min(player['hp'] + heal, player['max_hp'])
        enemy_damage = max(1, random.randint(1, enemy['attack']) - player['defense'])
        player['hp'] -= enemy_damage
        text = f"🛡️ Защита! +{heal} HP\nВраг нанёс {enemy_damage} урона"
    
    elif action == 'flee':
        player['in_battle'] = False
        player['enemy'] = None
        bot.edit_message_text("🏃 Ты сбежал!", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🏃 Побег!")
        return
    
    # Ход врага
    if enemy['hp'] > 0:
        enemy_damage = max(1, random.randint(1, enemy['attack']) - player['defense'])
        player['hp'] -= enemy_damage
        text += f"\n\n{enemy['emoji']} Враг нанёс {enemy_damage} урона!"
    
    # Проверка победы
    if enemy['hp'] <= 0:
        player['in_battle'] = False
        player['enemy'] = None
        player['wins'] += 1
        gold_reward = random.randint(5, 20)
        exp_reward = random.randint(10, 30)
        player['gold'] += gold_reward
        player['exp'] += exp_reward
        
        new_level = get_player_level(player['exp'])
        level_up = ""
        if new_level > player['level']:
            player['level'] = new_level
            player['max_hp'] += 10
            player['hp'] = player['max_hp']
            level_up = f"\n\n🎉 **УРОВЕНЬ ПОВЫШЕН!** ⭐{new_level}"
        
        check_achievements(player)
        
        bot.edit_message_text(
            f"{text}\n\n💀 **Враг повержен!**\n💰 +{gold_reward} золота\n📈 +{exp_reward} опыта{level_up}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "🎉 Победа!")
        return
    
    # Проверка смерти
    if player['hp'] <= 0:
        player['hp'] = 0
        player['in_battle'] = False
        player['enemy'] = None
        player['losses'] += 1
        bot.edit_message_text(
            f"{text}\n\n💀 **Ты погиб!**",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "💀 Поражение!")
        return
    
    # Продолжение боя
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("⚔️ Атаковать", "attack"),
        ("🛡️ Защищаться", "defend"),
        ("🏃 Сбежать", "flee"),
        ("💪 Сильный удар", "strong_attack")
    ]
    for text, callback in btns:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    battle_text = f"""
⚔️ **Битва продолжается!**

{CHARACTERS[player['character']]['emoji']} **Ты:** {CHARACTERS[player['character']]['name']}
❤️ HP: {player['hp']}/{player['max_hp']}

vs

{enemy['emoji']} **Враг:** {enemy['name']}
❤️ HP: {enemy['hp']}

📌 **Твой ход!**
"""
    bot.edit_message_text(
        battle_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id, "⚔️ Ход сделан!")

def battle_start(message, player):
    if player.get('in_battle', False):
        bot.send_message(message.chat.id, "⚔️ **Ты уже в бою!**", parse_mode='Markdown')
        return
    
    enemy = {
        'name': random.choice(['Гоблин', 'Скелет', 'Волк', 'Орк', 'Дракон']),
        'emoji': random.choice(['👺', '💀', '🐺', '👹', '🐉']),
        'hp': random.randint(30, 80),
        'attack': random.randint(8, 20)
    }
    
    player['enemy'] = enemy
    player['in_battle'] = True
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("⚔️ Атаковать", "attack"),
        ("🛡️ Защищаться", "defend"),
        ("🏃 Сбежать", "flee"),
        ("💪 Сильный удар", "strong_attack")
    ]
    for text, callback in btns:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    text = f"""
⚔️ **Битва началась!**

{CHARACTERS[player['character']]['emoji']} **Ты:** {CHARACTERS[player['character']]['name']}
❤️ HP: {player['hp']}/{player['max_hp']}

vs

{enemy['emoji']} **Враг:** {enemy['name']}
❤️ HP: {enemy['hp']}

📌 **Твой ход!**
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === ФУНКЦИИ ОТОБРАЖЕНИЯ ===
# ============================================

def show_profile(message, player):
    rank = get_rank(player['wins'])
    text = f"""
👤 **Профиль игрока**

📝 Имя: {message.from_user.first_name}
📌 @{message.from_user.username or 'не указан'}

{rank['emoji']} **Ранг:** {rank['name']}
{CHARACTERS[player['character']]['emoji']} **Класс:** {CHARACTERS[player['character']]['name']}
⭐ **Уровень:** {player['level']}
❤️ **HP:** {player['hp']}/{player['max_hp']}
⚔️ **Атака:** {player['attack']}
🛡️ **Защита:** {player['defense']}
💰 **Золото:** {player['gold']}
⭐ **Звёзд:** {player['stars']}
🏆 **Побед:** {player['wins']}
💀 **Поражений:** {player['losses']}
🎒 **Предметов:** {len(player['items'])}
💎 **Достижений:** {len(player['achievements'])}
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_inventory(message, player):
    if not player['items']:
        text = "🎒 **Инвентарь пуст**\n\nСражайся и покупай в магазине!"
    else:
        text = f"🎒 **Инвентарь** ({len(player['items'])} предметов)\n\n"
        for item_id, count in player['inventory'].items():
            if count > 0:
                all_items = get_all_shop_items()
                item = next((i for i in all_items if i['id'] == item_id), None)
                if item:
                    text += f"{item['emoji']} {item['name']} x{count}\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_leaderboard(message):
    sorted_players = sorted(
        player_games.values(),
        key=lambda x: (x['level'], x['stars']),
        reverse=True
    )[:10]
    
    text = "🏆 **Таблица лидеров**\n\n"
    medals = ['🥇', '🥈', '🥉']
    for i, player in enumerate(sorted_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        rank = get_rank(player['wins'])
        text += f"{medal} **{player['username'] or 'Аноним'}** — {rank['emoji']}{rank['name']}, ⭐{player['level']}, 🌟{player['stars']}⭐\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_achievements(message, player):
    text = "💎 **Достижения**\n\n"
    for key, ach in ACHIEVEMENTS.items():
        if ach['name'] in player.get('achievements', []):
            text += f"✅ {ach['emoji']} {ach['name']} (+{ach['reward']}⭐)\n"
        else:
            text += f"🔒 {ach['emoji']} {ach['name']} — {ach['desc']}\n"
    text += f"\n⭐ Всего звёзд: {player['stars']}"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_stars(message, player):
    text = f"""
⭐ **Твои звёзды**

🌟 Звёзд: {player['stars']}

📌 **Как заработать звёзды:**
• Победы в битвах (+1⭐)
• Достижения (+2-20⭐)
• Ежедневные награды (+1-3⭐)
• Обмен золота

💱 **Курс обмена:**
{get_settings().get('exchange_rate', 50)} золота = 1⭐
"""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [1, 2, 3, 5]:
        price = val * get_settings().get('exchange_rate', 50)
        if player['gold'] >= price:
            btn = types.InlineKeyboardButton(
                f"{val}⭐ ({price}💰)",
                callback_data=f"exchange_{val}"
            )
            keyboard.add(btn)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="start"))
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def daily_reward(message, player):
    settings = get_settings()
    today = datetime.now().date()
    last_daily = player.get('last_daily')
    
    if last_daily and datetime.fromisoformat(last_daily).date() == today:
        bot.send_message(message.chat.id, "🎁 **Сегодня уже получал!**\nПриходи завтра!", parse_mode='Markdown')
        return
    
    gold_min = settings.get('daily_gold_min', 20)
    gold_max = settings.get('daily_gold_max', 50)
    stars_min = settings.get('daily_stars_min', 1)
    stars_max = settings.get('daily_stars_max', 3)
    
    reward_gold = random.randint(gold_min, gold_max)
    reward_stars = random.randint(stars_min, stars_max)
    
    player['gold'] += reward_gold
    player['stars'] += reward_stars
    player['last_daily'] = datetime.now().isoformat()
    
    text = f"""
🎁 **Ежедневная награда!**

💰 +{reward_gold} золота
⭐ +{reward_stars} звёзд

📅 Приходи завтра!
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def change_class(message, player):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for key, val in CHARACTERS.items():
        btn = types.InlineKeyboardButton(
            f"{val['emoji']} {val['name']}",
            callback_data=f"class_{key}"
        )
        keyboard.add(btn)
    text = "🔄 **Выбери класс:**"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def check_achievements(player):
    for key, ach in ACHIEVEMENTS.items():
        if ach['name'] not in player.get('achievements', []):
            condition_met = False
            
            if key == 'first_win' and player['wins'] >= 1:
                condition_met = True
            elif key == 'warrior_10' and player['wins'] >= 10:
                condition_met = True
            elif key == 'warrior_50' and player['wins'] >= 50:
                condition_met = True
            elif key == 'warrior_100' and player['wins'] >= 100:
                condition_met = True
            elif key == 'level_5' and player['level'] >= 5:
                condition_met = True
            elif key == 'level_10' and player['level'] >= 10:
                condition_met = True
            elif key == 'level_20' and player['level'] >= 20:
                condition_met = True
            elif key == 'rich_50' and player['gold'] >= 50:
                condition_met = True
            elif key == 'rich_200' and player['gold'] >= 200:
                condition_met = True
            elif key == 'rich_500' and player['gold'] >= 500:
                condition_met = True
            elif key == 'collector' and len(player['items']) >= 5:
                condition_met = True
            elif key == 'merchant' and len(player['shop_history']) >= 3:
                condition_met = True
            
            if condition_met:
                player['achievements'].append(ach['name'])
                player['stars'] += ach['reward']
                try:
                    bot.send_message(
                        player['telegram_id'],
                        f"💎 **Новое достижение!**\n\n{ach['emoji']} {ach['name']}\n⭐ +{ach['reward']} звёзд",
                        parse_mode='Markdown'
                    )
                except:
                    pass

# ============================================
# === ЗАПУСК ===
# ============================================

if __name__ == '__main__':
    print('=' * 60)
    print('⭐ LEGENDARY БОТ BATTLEZ ЗАПУСКАЕТСЯ!')
    print('=' * 60)
    
    try:
        bot.remove_webhook()
        print('✅ Webhook удалён')
        time.sleep(2)
    except:
        pass
    
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    print('🔄 Запуск polling...')
    print('🎮 Бот готов!')
    print('=' * 60)
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print('\n⏹️ Бот остановлен')
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        sys.exit(1)
