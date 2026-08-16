# bot.py
import os
import sys
import random
import time
import threading
import json
import requests
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
# === ВЕБ-СЕРВЕР ДЛЯ ПОРТА ===
# ============================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f'✅ Веб-сервер запущен на порту {port}')
    server.serve_forever()

# ============================================
# === KEEP-ALIVE ===
# ============================================

def keep_alive():
    port = int(os.environ.get('PORT', 10000))
    url = f'http://localhost:{port}/'
    while True:
        try:
            requests.get(url, timeout=5)
            print(f'✅ Keep-alive пинг отправлен в {datetime.now().strftime("%H:%M:%S")}')
        except Exception as e:
            print(f'⚠️ Ошибка пинга: {e}')
        time.sleep(300)

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
# === НАСТРОЙКИ ===
# ============================================

SETTINGS_FILE = 'settings.json'

DEFAULT_SETTINGS = {
    'exchange_rate': 30,
    'stars_to_gold_rate': 15,
    'stars_to_telegram_stars': 10,
    'daily_gold_min': 20,
    'daily_gold_max': 50,
    'daily_stars_min': 1,
    'daily_stars_max': 3,
    'zpremium_price_7': 5,
    'zpremium_price_30': 15,
    'zpremium_price_90': 35,
    'zpremium_channel_link': 'https://t.me/+Jiws0_2AxaUzOTUy',
    'zpremium_active': True
}

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            for key in DEFAULT_SETTINGS:
                if key not in settings:
                    settings[key] = DEFAULT_SETTINGS[key]
            return settings
    except:
        return dict(DEFAULT_SETTINGS)

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

SETTINGS = load_settings()

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
        'total_battles': 0,
        'shop_history': [],
        'joined_at': datetime.now().isoformat(),
        'zpremium_expires': None,
        'discount': 0,
        'premium_days': 0
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

def get_all_shop_items():
    all_items = []
    for cat in SHOP.values():
        all_items.extend(cat['items'])
    return all_items

# ============================================
# === ZPREMIUM ФУНКЦИИ ===
# ============================================

def check_zpremium(player):
    if not player.get('zpremium_expires'):
        return False
    try:
        expires = datetime.fromisoformat(player['zpremium_expires'])
        return datetime.now() < expires
    except:
        return False

def get_zpremium_remaining(player):
    if not player.get('zpremium_expires'):
        return 0
    try:
        expires = datetime.fromisoformat(player['zpremium_expires'])
        diff = expires - datetime.now()
        return max(0, diff.days)
    except:
        return 0

def activate_zpremium(player, days):
    price_key = f'zpremium_price_{days}'
    price = SETTINGS.get(price_key, 5 if days == 7 else 15 if days == 30 else 35)
    
    if player['stars'] < price:
        return False, f"❌ Недостаточно звёзд! Нужно {price}⭐"
    
    player['stars'] -= price
    
    current_expires = player.get('zpremium_expires')
    if current_expires and datetime.fromisoformat(current_expires) > datetime.now():
        new_expires = datetime.fromisoformat(current_expires) + timedelta(days=days)
    else:
        new_expires = datetime.now() + timedelta(days=days)
    
    player['zpremium_expires'] = new_expires.isoformat()
    
    channel_link = SETTINGS.get('zpremium_channel_link', 'https://t.me/+Jiws0_2AxaUzOTUy')
    return True, f"✅ ZPremium активирован на {days} дней!\n\n🔗 Ссылка на канал: {channel_link}"

# ============================================
# === КЛАВИАТУРЫ ===
# ============================================

def get_main_keyboard(user_id, player):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("⚔️ Битва", "battle"),
        ("👤 Профиль", "profile"),
        ("🏪 Магазин", "shop"),
        ("⭐ Звёзды", "stars"),
        ("🎒 Инвентарь", "inventory"),
        ("🏆 Лидеры", "leaderboard"),
        ("💎 Достижения", "achievements"),
        ("🎁 Ежедневно", "daily"),
        ("🔄 Сменить класс", "change_class"),
    ]
    for text, callback in btns:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    keyboard.add(types.InlineKeyboardButton("🌐 Сайт", url="https://battle-z.vercel.app/"))
    
    if user_id in ADMIN_IDS:
        keyboard.add(types.InlineKeyboardButton("🔧 Админ-панель", callback_data="admin_panel"))
    
    return keyboard

def get_admin_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("📊 Статистика", "admin_stats"),
        ("👥 Пользователи", "admin_users"),
        ("💱 Курс обмена", "admin_exchange"),
        ("⭐ Stars курс", "admin_stars_rate"),
        ("👑 ZPremium", "admin_zpremium"),
        ("🎫 Промокоды", "admin_promo"),
        ("🎮 Выдать предмет", "admin_give_item"),
        ("💰 Выдать звёзды", "admin_give_stars"),
        ("📢 Рассылка", "admin_broadcast"),
        ("🔄 Сброс настроек", "admin_reset"),
        ("🔙 Главное меню", "back_to_menu")
    ]
    for text, callback in btns:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    return keyboard

def get_zpremium_plans_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    price_7 = SETTINGS.get('zpremium_price_7', 5)
    price_30 = SETTINGS.get('zpremium_price_30', 15)
    price_90 = SETTINGS.get('zpremium_price_90', 35)
    
    keyboard.add(types.InlineKeyboardButton(f"⭐ 7 дней — {price_7}⭐", callback_data="zpremium_7_days"))
    keyboard.add(types.InlineKeyboardButton(f"🌟 30 дней — {price_30}⭐", callback_data="zpremium_30_days"))
    keyboard.add(types.InlineKeyboardButton(f"👑 90 дней — {price_90}⭐", callback_data="zpremium_90_days"))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_profile"))
    return keyboard

def get_shop_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for key, cat in SHOP.items():
        keyboard.add(types.InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}",
            callback_data=f"shop_{key}"
        ))
    keyboard.add(types.InlineKeyboardButton("⭐ Купить за Stars", callback_data="shop_real"))
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    return keyboard

def get_shop_category_keyboard(category):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    items = SHOP[category]['items']
    for item in items:
        keyboard.add(types.InlineKeyboardButton(
            f"{item['emoji']} {item['name']} — {item['price_stars']}⭐",
            callback_data=f"buy_{item['id']}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back"))
    return keyboard

def get_shop_real_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    all_items = get_all_shop_items()
    for item in all_items:
        if 'price_real' in item:
            keyboard.add(types.InlineKeyboardButton(
                f"{item['emoji']} {item['name']} — {item['price_real']}⭐",
                callback_data=f"buy_real_{item['id']}"
            ))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back"))
    return keyboard

def get_stars_keyboard(player):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [1, 2, 3, 5, 10]:
        price = val * SETTINGS.get('exchange_rate', 30)
        if player['gold'] >= price:
            keyboard.add(types.InlineKeyboardButton(
                f"{val}⭐ ({price}💰)",
                callback_data=f"buy_stars_{val}"
            ))
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    return keyboard

def get_battle_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("⚔️ Атаковать", "attack"),
        ("🛡️ Защищаться", "defend"),
        ("💪 Сильный удар", "strong_attack"),
        ("🏃 Сбежать", "flee")
    ]
    for text, callback in btns:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    return keyboard

def get_change_class_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for key, val in CHARACTERS.items():
        keyboard.add(types.InlineKeyboardButton(
            f"{val['emoji']} {val['name']}",
            callback_data=f"class_{key}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    return keyboard

# ============================================
# === КОМАНДЫ БОТА ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if user_id not in player_games:
        player_games[user_id] = create_player(user_id, message.from_user.username)
    
    player = player_games[user_id]
    rank = get_rank(player['wins'])
    
    keyboard = get_main_keyboard(user_id, player)
    
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
# === ПРОФИЛЬ ===
# ============================================

def show_profile(message, player):
    rank = get_rank(player['wins'])
    is_premium = check_zpremium(player)
    days_left = get_zpremium_remaining(player)
    
    premium_status = "✅ Активен" if is_premium else "❌ Неактивен"
    premium_days = f" ({days_left} дн.)" if is_premium else ""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton("👑 ZPremium", callback_data="zpremium_menu"))
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    
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

👑 **ZPremium:** {premium_status}{premium_days}
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === ZPREMIUM МЕНЮ ===
# ============================================

def show_zpremium_menu(message):
    if not SETTINGS.get('zpremium_active', True):
        bot.send_message(message.chat.id, "❌ ZPremium временно отключён администратором")
        return
    
    keyboard = get_zpremium_plans_keyboard()
    price_7 = SETTINGS.get('zpremium_price_7', 5)
    price_30 = SETTINGS.get('zpremium_price_30', 15)
    price_90 = SETTINGS.get('zpremium_price_90', 35)
    
    text = f"""
👑 **ZPremium — Приватный канал BattleZ**

📌 **Что даёт ZPremium:**
• 🔗 Доступ к приватному каналу
• 🎁 Эксклюзивные промокоды
• 📰 Новости первыми
• 🗣️ Общение с командой
• 🏆 Закрытые ивенты
• 💎 Специальные предложения

📌 **Цены:**
⭐ 7 дней — {price_7}⭐
🌟 30 дней — {price_30}⭐
👑 90 дней — {price_90}⭐

📌 **Выбери план:**
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === ОБРАБОТЧИК КОЛБЭКОВ (ВСЕ КНОПКИ) ===
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    message = call.message
    
    print(f'📩 Получен callback: {data} от {user_id}')
    
    # ==========================================
    # === АДМИН-ПАНЕЛЬ ===
    # ==========================================
    if data == 'admin_panel':
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён!", show_alert=True)
            return
        show_admin_panel(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_stats':
        if user_id not in ADMIN_IDS:
            return
        admin_stats(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_users':
        if user_id not in ADMIN_IDS:
            return
        admin_users(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_exchange':
        if user_id not in ADMIN_IDS:
            return
        admin_exchange(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_stars_rate':
        if user_id not in ADMIN_IDS:
            return
        admin_stars_rate(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_zpremium':
        if user_id not in ADMIN_IDS:
            return
        admin_zpremium_handler(call, message)
        return
    
    if data == 'admin_promo':
        if user_id not in ADMIN_IDS:
            return
        admin_promo_handler(call)
        return
    
    if data == 'admin_give_item':
        if user_id not in ADMIN_IDS:
            return
        admin_give_item(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_give_stars':
        if user_id not in ADMIN_IDS:
            return
        admin_give_stars(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_broadcast':
        if user_id not in ADMIN_IDS:
            return
        admin_broadcast(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'admin_reset':
        if user_id not in ADMIN_IDS:
            return
        admin_reset(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'back_to_menu':
        start(message)
        bot.answer_callback_query(call.id)
        return
    
    # ==========================================
    # === ZPREMIUM ===
    # ==========================================
    if data == 'zpremium_menu':
        show_zpremium_menu(message)
        bot.answer_callback_query(call.id)
        return
    
    if data in ['zpremium_7_days', 'zpremium_30_days', 'zpremium_90_days']:
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        
        days_map = {
            'zpremium_7_days': 7,
            'zpremium_30_days': 30,
            'zpremium_90_days': 90
        }
        days = days_map[data]
        success, msg = activate_zpremium(player, days)
        
        if success:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(
                "🔗 Перейти в канал",
                url=SETTINGS.get('zpremium_channel_link', 'https://t.me/+Jiws0_2AxaUzOTUy')
            ))
            keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_profile"))
            bot.edit_message_text(
                msg,
                message.chat.id,
                message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    if data == 'back_to_profile':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        show_profile(message, player)
        bot.answer_callback_query(call.id)
        return
    
    # ==========================================
    # === МАГАЗИН ===
    # ==========================================
    if data == 'shop':
        show_shop(message)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('shop_'):
        category = data.replace('shop_', '')
        if category in SHOP:
            show_shop_category(message, category)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'shop_back':
        show_shop(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'shop_real':
        show_shop_real(message)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('buy_'):
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        item_id = data.replace('buy_', '')
        success, msg = buy_item(player, item_id)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if success:
            for cat_key, cat in SHOP.items():
                if any(i['id'] == item_id for i in cat['items']):
                    show_shop_category(message, cat_key)
                    break
        return
    
    if data.startswith('buy_real_'):
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        item_id = data.replace('buy_real_', '')
        success, msg = buy_with_real_stars(player, item_id)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if success:
            show_shop_real(message)
        return
    
    # ==========================================
    # === ЗВЁЗДЫ ===
    # ==========================================
    if data == 'stars':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        show_stars(message, player)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('buy_stars_'):
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        amount = int(data.replace('buy_stars_', ''))
        price = amount * SETTINGS.get('exchange_rate', 30)
        if player['gold'] >= price:
            player['gold'] -= price
            player['stars'] += amount
            bot.answer_callback_query(call.id, f"✅ +{amount}⭐ ( -{price}💰)", show_alert=True)
            show_stars(message, player)
        else:
            bot.answer_callback_query(call.id, f"❌ Недостаточно золота! Нужно {price}💰", show_alert=True)
        return
    
    # ==========================================
    # === БИТВА ===
    # ==========================================
    if data in ['attack', 'defend', 'flee', 'strong_attack']:
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        handle_battle_action(call, player, data)
        return
    
    # ==========================================
    # === ОСТАЛЬНЫЕ ===
    # ==========================================
    if data == 'battle':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        battle_start(message, player)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'profile':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        show_profile(message, player)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'inventory':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        show_inventory(message, player)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'leaderboard':
        show_leaderboard(message)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'achievements':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        show_achievements(message, player)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'daily':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        daily_reward(message, player)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'change_class':
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
        change_class(message, player)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('class_'):
        if user_id not in player_games:
            player_games[user_id] = create_player(user_id, call.from_user.username)
        player = player_games[user_id]
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
                message.chat.id,
                message.message_id,
                parse_mode='Markdown'
            )
        return
    
    # ==========================================
    # === ЕСЛИ НИЧЕГО НЕ ПОДОШЛО ===
    # ==========================================
    bot.answer_callback_query(call.id, "⚠️ Команда не найдена", show_alert=True)

# ============================================
# === АДМИН-ПАНЕЛЬ ===
# ============================================

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Доступ запрещён!")
        return
    show_admin_panel(message)

def show_admin_panel(message):
    keyboard = get_admin_keyboard()
    
    text = f"""
🔧 **Админ-панель BattleZ**

💱 Курс: {SETTINGS.get('exchange_rate', 30)}💰 = 1⭐
⭐ Stars: {SETTINGS.get('stars_to_telegram_stars', 10)} Stars = 1⭐
👑 ZPremium: {'✅ Вкл' if SETTINGS.get('zpremium_active', True) else '❌ Выкл'}

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
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def admin_users(message):
    users = db.get_all_users()
    if not users:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
        bot.send_message(message.chat.id, "📭 Нет пользователей", reply_markup=keyboard)
        return
    
    text = "👥 **Последние пользователи:**\n\n"
    for u in users[:10]:
        text += f"👤 {u.get('username') or 'Аноним'}\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def admin_exchange(message):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [15, 20, 30, 40, 50, 60]:
        keyboard.add(types.InlineKeyboardButton(
            f"{val}💰 = 1⭐",
            callback_data=f"set_exchange_{val}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    text = f"""
💱 **Курс обмена золота**

📌 **Текущий курс:** {SETTINGS.get('exchange_rate', 30)} золота = 1⭐

Выбери новый курс:
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def admin_stars_rate(message):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [5, 10, 15, 20, 25, 30]:
        keyboard.add(types.InlineKeyboardButton(
            f"{val}⭐ = 1⭐",
            callback_data=f"set_stars_rate_{val}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    text = f"""
⭐ **Курс обмена Telegram Stars**

📌 **Текущий курс:** {SETTINGS.get('stars_to_telegram_stars', 10)} Telegram Stars = 1⭐

Выбери новый курс:
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def admin_give_item(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    all_items = get_all_shop_items()
    for item in all_items[:10]:
        keyboard.add(types.InlineKeyboardButton(
            f"{item['emoji']} {item['name']}",
            callback_data=f"give_item_{item['id']}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    bot.send_message(message.chat.id, "🎮 **Выдать предмет пользователю**\n\nВыбери предмет:", parse_mode='Markdown', reply_markup=keyboard)

def admin_give_stars(message):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for val in [10, 25, 50, 100, 250, 500]:
        keyboard.add(types.InlineKeyboardButton(
            f"{val}⭐",
            callback_data=f"give_stars_{val}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    
    bot.send_message(message.chat.id, "💰 **Выдать звёзды пользователю**\n\nВыбери количество:", parse_mode='Markdown', reply_markup=keyboard)

def admin_broadcast(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    bot.send_message(message.chat.id, "📢 **Рассылка**\n\nВведи текст для рассылки:", reply_markup=keyboard)

def admin_reset(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton("✅ Да, сбросить", callback_data="reset_confirm"))
    keyboard.add(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel"))
    
    bot.send_message(message.chat.id, "⚠️ **Сбросить все настройки?**", parse_mode='Markdown', reply_markup=keyboard)

def admin_zpremium_handler(call, message):
    if call.from_user.id not in ADMIN_IDS:
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        ("⭐ 7 дней", "set_zpremium_7"),
        ("🌟 30 дней", "set_zpremium_30"),
        ("👑 90 дней", "set_zpremium_90"),
        ("🔗 Ссылка на канал", "set_zpremium_link"),
        ("🔄 Вкл/Выкл", "toggle_zpremium"),
        ("🔙 Назад", "admin_panel")
    ]
    for text, callback in btns:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    price_7 = SETTINGS.get('zpremium_price_7', 5)
    price_30 = SETTINGS.get('zpremium_price_30', 15)
    price_90 = SETTINGS.get('zpremium_price_90', 35)
    is_active = SETTINGS.get('zpremium_active', True)
    channel_link = SETTINGS.get('zpremium_channel_link', 'https://t.me/+Jiws0_2AxaUzOTUy')
    
    text = f"""
👑 **ZPremium — Настройки**

📌 **Цены:**
⭐ 7 дней — {price_7}⭐
🌟 30 дней — {price_30}⭐
👑 90 дней — {price_90}⭐

📌 **Статус:** {'✅ Активен' if is_active else '❌ Отключён'}
🔗 **Канал:** {channel_link}

📌 **Выбери действие:**
"""
    bot.edit_message_text(
        text,
        message.chat.id,
        message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id)

def admin_promo_handler(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    
    # Здесь можно добавить логику промокодов
    bot.answer_callback_query(call.id, "🎫 Раздел промокодов в разработке!", show_alert=True)

# ============================================
# === ОСТАЛЬНЫЕ ФУНКЦИИ ===
# ============================================

def buy_item(player, item_id):
    all_items = get_all_shop_items()
    item = next((i for i in all_items if i['id'] == item_id), None)
    
    if not item:
        return False, "❌ Товар не найден"
    
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
    all_items = get_all_shop_items()
    item = next((i for i in all_items if i['id'] == item_id), None)
    
    if not item:
        return False, "❌ Товар не найден"
    
    price_real = item.get('price_real', 1)
    
    if item_id not in player['inventory']:
        player['inventory'][item_id] = 0
    player['inventory'][item_id] += 1
    player['items'].append(item['name'])
    
    return True, f"✅ Куплено: {item['emoji']} {item['name']} за {price_real}⭐ реальных звёзд!"

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
    
    keyboard = get_battle_keyboard()
    
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

def handle_battle_action(call, player, action):
    if not player.get('in_battle', False):
        bot.answer_callback_query(call.id, "❌ Ты не в бою!", show_alert=True)
        return
    
    enemy = player['enemy']
    message = call.message
    chat_id = message.chat.id
    msg_id = message.message_id
    
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
        bot.edit_message_text("🏃 Ты сбежал!", chat_id, msg_id)
        bot.answer_callback_query(call.id, "🏃 Побег!")
        return
    
    if enemy['hp'] > 0:
        enemy_damage = max(1, random.randint(1, enemy['attack']) - player['defense'])
        player['hp'] -= enemy_damage
        text += f"\n\n{enemy['emoji']} Враг нанёс {enemy_damage} урона!"
    
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
        
        bot.edit_message_text(
            f"{text}\n\n💀 **Враг повержен!**\n💰 +{gold_reward} золота\n📈 +{exp_reward} опыта{level_up}",
            chat_id, msg_id, parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "🎉 Победа!")
        return
    
    if player['hp'] <= 0:
        player['hp'] = 0
        player['in_battle'] = False
        player['enemy'] = None
        player['losses'] += 1
        bot.edit_message_text(f"{text}\n\n💀 **Ты погиб!**", chat_id, msg_id, parse_mode='Markdown')
        bot.answer_callback_query(call.id, "💀 Поражение!")
        return
    
    keyboard = get_battle_keyboard()
    
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
        chat_id,
        msg_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id, "⚔️ Ход сделан!")

def show_shop(message):
    keyboard = get_shop_keyboard()
    bot.send_message(message.chat.id, "🏪 **Магазин BattleZ**\n\nВыбери категорию:", parse_mode='Markdown', reply_markup=keyboard)

def show_shop_category(message, category):
    keyboard = get_shop_category_keyboard(category)
    text = f"🏪 **{SHOP[category]['emoji']} {SHOP[category]['name']}**\n\nВыбери товар:"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def show_shop_real(message):
    keyboard = get_shop_real_keyboard()
    text = f"⭐ **Магазин за Telegram Stars**\n\nКурс: {SETTINGS.get('stars_to_telegram_stars', 10)} Telegram Stars = 1⭐\n\n📌 Выбери товар:"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def show_stars(message, player):
    keyboard = get_stars_keyboard(player)
    
    text = f"""
⭐ **Твои звёзды**

🌟 Звёзд: {player['stars']}
💰 Золота: {player['gold']}

💱 **Курс обмена:**
{SETTINGS.get('exchange_rate', 30)}💰 = 1⭐

📌 **Нажми на кнопку, чтобы обменять:**
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

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
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

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
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def show_achievements(message, player):
    text = "💎 **Достижения**\n\n"
    for key, ach in ACHIEVEMENTS.items():
        if ach['name'] in player.get('achievements', []):
            text += f"✅ {ach['emoji']} {ach['name']} (+{ach['reward']}⭐)\n"
        else:
            text += f"🔒 {ach['emoji']} {ach['name']} — {ach['desc']}\n"
    text += f"\n⭐ Всего звёзд: {player['stars']}"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def daily_reward(message, player):
    today = datetime.now().date()
    last_daily = player.get('last_daily')
    
    if last_daily and datetime.fromisoformat(last_daily).date() == today:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
        bot.send_message(message.chat.id, "🎁 **Сегодня уже получал!**\nПриходи завтра!", parse_mode='Markdown', reply_markup=keyboard)
        return
    
    reward_gold = random.randint(SETTINGS.get('daily_gold_min', 20), SETTINGS.get('daily_gold_max', 50))
    reward_stars = random.randint(SETTINGS.get('daily_stars_min', 1), SETTINGS.get('daily_stars_max', 3))
    
    player['gold'] += reward_gold
    player['stars'] += reward_stars
    player['last_daily'] = datetime.now().isoformat()
    
    text = f"""
🎁 **Ежедневная награда!**

💰 +{reward_gold} золота
⭐ +{reward_stars} звёзд

📅 Приходи завтра!
"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def change_class(message, player):
    keyboard = get_change_class_keyboard()
    bot.send_message(message.chat.id, "🔄 **Выбери класс:**", parse_mode='Markdown', reply_markup=keyboard)

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
    except Exception as e:
        print(f'⚠️ Ошибка удаления webhook: {e}')
    
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    print('✅ Keep-alive запущен (каждые 5 минут)')
    
    print('🔄 Запуск polling...')
    print('🎮 Бот готов!')
    print('=' * 60)
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print('\n⏹️ Бот остановлен')
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        traceback.print_exc()
        sys.exit(1)
