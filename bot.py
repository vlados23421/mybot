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
from functools import lru_cache
from collections import defaultdict

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

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

# ============================================
# === ИГРОВЫЕ ДАННЫЕ ===
# ============================================

# Классы персонажей
CHARACTERS = {
    'warrior': {'name': 'Воин', 'emoji': '⚔️', 'hp': 120, 'attack': 15, 'defense': 10},
    'mage': {'name': 'Маг', 'emoji': '🔮', 'hp': 80, 'attack': 25, 'defense': 5},
    'rogue': {'name': 'Разбойник', 'emoji': '🗡️', 'hp': 90, 'attack': 20, 'defense': 8},
    'paladin': {'name': 'Паладин', 'emoji': '🛡️', 'hp': 140, 'attack': 12, 'defense': 15},
    'archer': {'name': 'Лучник', 'emoji': '🏹', 'hp': 85, 'attack': 22, 'defense': 6},
    'warlock': {'name': 'Чернокнижник', 'emoji': '🌀', 'hp': 75, 'attack': 28, 'defense': 4}
}

# ============================================
# === МАГАЗИН ===
# ============================================

SHOP = {
    'weapons': {
        'name': 'Оружие',
        'emoji': '⚔️',
        'items': [
            {'id': 'sword', 'name': 'Стальной меч', 'emoji': '🗡️', 'price': 50, 'stats': {'attack': 5}},
            {'id': 'bow', 'name': 'Длинный лук', 'emoji': '🏹', 'price': 40, 'stats': {'attack': 4}},
            {'id': 'staff', 'name': 'Магический посох', 'emoji': '🔮', 'price': 60, 'stats': {'attack': 6}},
            {'id': 'axe', 'name': 'Боевой топор', 'emoji': '🪓', 'price': 55, 'stats': {'attack': 7}},
            {'id': 'dagger', 'name': 'Кинжал тьмы', 'emoji': '🗡️', 'price': 45, 'stats': {'attack': 5}},
            {'id': 'hammer', 'name': 'Молот грома', 'emoji': '🔨', 'price': 70, 'stats': {'attack': 8}},
        ]
    },
    'armor': {
        'name': 'Броня',
        'emoji': '🛡️',
        'items': [
            {'id': 'leather', 'name': 'Кожаная броня', 'emoji': '🥾', 'price': 30, 'stats': {'defense': 3}},
            {'id': 'chainmail', 'name': 'Кольчуга', 'emoji': '⛓️', 'price': 50, 'stats': {'defense': 5}},
            {'id': 'plate', 'name': 'Латы', 'emoji': '🛡️', 'price': 80, 'stats': {'defense': 8}},
            {'id': 'robe', 'name': 'Магическая мантия', 'emoji': '👘', 'price': 45, 'stats': {'defense': 4}},
            {'id': 'shield', 'name': 'Щит стража', 'emoji': '🛡️', 'price': 60, 'stats': {'defense': 6}},
        ]
    },
    'potions': {
        'name': 'Зелья',
        'emoji': '🧪',
        'items': [
            {'id': 'health_potion', 'name': 'Зелье здоровья', 'emoji': '❤️', 'price': 20, 'stats': {'heal': 30}},
            {'id': 'big_health', 'name': 'Большое зелье', 'emoji': '💖', 'price': 40, 'stats': {'heal': 60}},
            {'id': 'exp_potion', 'name': 'Зелье опыта', 'emoji': '📈', 'price': 35, 'stats': {'exp': 20}},
        ]
    },
    'boosts': {
        'name': 'Бусты',
        'emoji': '⚡',
        'items': [
            {'id': 'attack_boost', 'name': 'Буст атаки', 'emoji': '⚔️', 'price': 25, 'stats': {'attack_boost': 5}},
            {'id': 'defense_boost', 'name': 'Буст защиты', 'emoji': '🛡️', 'price': 25, 'stats': {'defense_boost': 5}},
            {'id': 'exp_boost', 'name': 'Буст опыта x2', 'emoji': '📈', 'price': 30, 'stats': {'exp_boost': True}},
        ]
    },
    'skins': {
        'name': 'Скины',
        'emoji': '🎨',
        'items': [
            {'id': 'golden', 'name': 'Золотой скин', 'emoji': '🌟', 'price': 100, 'stats': {'skin': 'golden'}},
            {'id': 'dark', 'name': 'Тёмный скин', 'emoji': '🌙', 'price': 80, 'stats': {'skin': 'dark'}},
            {'id': 'fire', 'name': 'Огненный скин', 'emoji': '🔥', 'price': 90, 'stats': {'skin': 'fire'}},
        ]
    }
}

# ============================================
# === ДОСТИЖЕНИЯ ===
# ============================================

ACHIEVEMENTS = {
    'first_win': {'name': 'Первая победа', 'emoji': '🎯', 'reward': 10, 'desc': 'Одень первую победу'},
    'warrior_10': {'name': '10 побед', 'emoji': '⚔️', 'reward': 25, 'desc': 'Одень 10 побед'},
    'warrior_50': {'name': '50 побед', 'emoji': '🏆', 'reward': 50, 'desc': 'Одень 50 побед'},
    'warrior_100': {'name': '100 побед', 'emoji': '👑', 'reward': 100, 'desc': 'Одень 100 побед'},
    'level_5': {'name': '5 уровень', 'emoji': '⭐', 'reward': 15, 'desc': 'Достигни 5 уровня'},
    'level_10': {'name': '10 уровень', 'emoji': '🌟', 'reward': 30, 'desc': 'Достигни 10 уровня'},
    'level_20': {'name': '20 уровень', 'emoji': '💫', 'reward': 60, 'desc': 'Достигни 20 уровня'},
    'rich_50': {'name': '50 золота', 'emoji': '💰', 'reward': 10, 'desc': 'Накопи 50 золота'},
    'rich_200': {'name': '200 золота', 'emoji': '💎', 'reward': 30, 'desc': 'Накопи 200 золота'},
    'rich_500': {'name': '500 золота', 'emoji': '👑', 'reward': 60, 'desc': 'Накопи 500 золота'},
    'killer_10': {'name': 'Убийца гоблинов', 'emoji': '👺', 'reward': 20, 'desc': 'Убей 10 гоблинов'},
    'killer_dragon': {'name': 'Драконоборец', 'emoji': '🐉', 'reward': 50, 'desc': 'Убей дракона'},
    'collector': {'name': 'Коллекционер', 'emoji': '🎒', 'reward': 30, 'desc': 'Собери 5 предметов'},
    'merchant': {'name': 'Торговец', 'emoji': '🏪', 'reward': 25, 'desc': 'Купи 3 предмета в магазине'},
}

# ============================================
# === ОПТИМИЗАЦИЯ: КЭШ ===
# ============================================

player_cache = {}
cache_timeout = 300  # 5 минут

def get_player(telegram_id, username=None):
    """Получить игрока с кэшированием"""
    now = time.time()
    
    if telegram_id in player_cache:
        player, timestamp = player_cache[telegram_id]
        if now - timestamp < cache_timeout:
            return player
    
    # Создаём нового игрока
    player = create_player(telegram_id, username)
    player_cache[telegram_id] = (player, now)
    return player

def save_player(telegram_id, player):
    """Сохранить игрока в кэш"""
    player_cache[telegram_id] = (player, time.time())

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
        'gold': 50,
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
        'kills': {},
        'shop_history': [],
        'joined_at': datetime.now().isoformat()
    }

def get_player_level(exp):
    return 1 + exp // 50

def get_next_level_exp(level):
    return level * 50

# ============================================
# === ФУНКЦИИ МАГАЗИНА ===
# ============================================

def get_shop_items(category=None):
    if category and category in SHOP:
        return SHOP[category]['items']
    all_items = []
    for cat in SHOP.values():
        all_items.extend(cat['items'])
    return all_items

def buy_item(player, item_id):
    all_items = get_shop_items()
    item = next((i for i in all_items if i['id'] == item_id), None)
    
    if not item:
        return False, "❌ Товар не найден"
    
    if player['gold'] < item['price']:
        return False, f"❌ Недостаточно золота! Нужно {item['price']}"
    
    player['gold'] -= item['price']
    
    # Добавляем в инвентарь
    if item_id not in player['inventory']:
        player['inventory'][item_id] = 0
    player['inventory'][item_id] += 1
    player['items'].append(item['name'])
    player['shop_history'].append({
        'item': item['name'],
        'price': item['price'],
        'time': datetime.now().isoformat()
    })
    
    return True, f"✅ Куплено: {item['emoji']} {item['name']}"

def use_item(player, item_id):
    all_items = get_shop_items()
    item = next((i for i in all_items if i['id'] == item_id), None)
    
    if not item:
        return False, "❌ Товар не найден"
    
    if player['inventory'].get(item_id, 0) <= 0:
        return False, "❌ У вас нет этого предмета"
    
    stats = item.get('stats', {})
    
    # Применяем эффекты
    if 'heal' in stats:
        player['hp'] = min(player['hp'] + stats['heal'], player['max_hp'])
        player['inventory'][item_id] -= 1
        return True, f"❤️ Восстановлено {stats['heal']} HP"
    
    elif 'exp' in stats:
        player['exp'] += stats['exp']
        player['inventory'][item_id] -= 1
        return True, f"📈 Получено {stats['exp']} опыта"
    
    elif 'attack_boost' in stats:
        player['attack'] += stats['attack_boost']
        player['inventory'][item_id] -= 1
        return True, f"⚔️ Атака +{stats['attack_boost']}"
    
    elif 'defense_boost' in stats:
        player['defense'] += stats['defense_boost']
        player['inventory'][item_id] -= 1
        return True, f"🛡️ Защита +{stats['defense_boost']}"
    
    elif 'skin' in stats:
        player['skin'] = stats['skin']
        player['inventory'][item_id] -= 1
        return True, f"🎨 Скин изменён на {item['name']}"
    
    return False, "❌ Этот предмет нельзя использовать"

# ============================================
# === КОМАНДЫ БОТА ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    player = get_player(user_id, message.from_user.username)
    save_player(user_id, player)
    
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
    for text, callback in btns:
        if callback == "site":
            btn = types.InlineKeyboardButton(text, url="https://battle-z.vercel.app/")
        else:
            btn = types.InlineKeyboardButton(text, callback_data=callback)
        keyboard.add(btn)
    
    text = f"""
🎮 **Добро пожаловать в BattleZ!**

Привет, {message.from_user.first_name}! 👋

{CHARACTERS[player['character']]['emoji']} **Класс:** {CHARACTERS[player['character']]['name']}
❤️ **HP:** {player['hp']}/{player['max_hp']}
⭐ **Уровень:** {player['level']}
⭐ **Звёзд:** {player['stars']}
💰 **Золота:** {player['gold']}

📌 **Выбери действие:**
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === МАГАЗИН ===
# ============================================

@bot.message_handler(commands=['shop'])
def shop_command(message):
    show_shop(message)

def show_shop(message, category=None):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    if category:
        items = SHOP[category]['items']
        for item in items:
            btn = types.InlineKeyboardButton(
                f"{item['emoji']} {item['name']} — {item['price']}⭐",
                callback_data=f"buy_{item['id']}"
            )
            keyboard.add(btn)
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back")
        keyboard.add(btn_back)
        
        text = f"🏪 **{SHOP[category]['emoji']} {SHOP[category]['name']}**\n\nВыбери товар:"
    else:
        for key, cat in SHOP.items():
            btn = types.InlineKeyboardButton(
                f"{cat['emoji']} {cat['name']}",
                callback_data=f"shop_{key}"
            )
            keyboard.add(btn)
        text = "🏪 **Магазин BattleZ**\n\nВыбери категорию:"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

# ============================================
# === КОЛБЭКИ ===
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    player = get_player(user_id, call.from_user.username)
    
    # ===== МАГАЗИН =====
    if data == 'shop':
        show_shop(call.message)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('shop_'):
        category = data.replace('shop_', '')
        if category in SHOP:
            show_shop(call.message, category)
        bot.answer_callback_query(call.id)
        return
    
    if data == 'shop_back':
        show_shop(call.message)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith('buy_'):
        item_id = data.replace('buy_', '')
        success, msg = buy_item(player, item_id)
        save_player(user_id, player)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if success:
            show_shop(call.message, get_item_category(item_id))
        return
    
    # ===== ИСПОЛЬЗОВАТЬ ПРЕДМЕТ =====
    if data.startswith('use_'):
        item_id = data.replace('use_', '')
        success, msg = use_item(player, item_id)
        save_player(user_id, player)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    # ===== ОСТАЛЬНЫЕ КОМАНДЫ =====
    if data == 'battle':
        battle_start(call.message, player)
    elif data == 'profile':
        show_profile(call.message, player)
    elif data == 'inventory':
        show_inventory(call.message, player)
    elif data == 'leaderboard':
        show_leaderboard(call.message)
    elif data == 'achievements':
        show_achievements(call.message, player)
    elif data == 'stars':
        show_stars(call.message, player)
    elif data == 'daily':
        daily_reward(call.message, player)
    elif data == 'change_class':
        change_class(call.message, player)
    
    bot.answer_callback_query(call.id)

# ============================================
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
# ============================================

def get_item_category(item_id):
    for cat_key, cat in SHOP.items():
        for item in cat['items']:
            if item['id'] == item_id:
                return cat_key
    return None

def show_profile(message, player):
    text = f"""
👤 **Профиль игрока**

📝 Имя: {message.from_user.first_name}
📌 @{message.from_user.username or 'не указан'}

{CHARACTERS[player['character']]['emoji']} **{CHARACTERS[player['character']]['name']}**
⭐ Уровень: {player['level']}
❤️ HP: {player['hp']}/{player['max_hp']}
⚔️ Атака: {player['attack']}
🛡️ Защита: {player['defense']}
💰 Золото: {player['gold']}
⭐ Звёзды: {player['stars']}
🏆 Побед: {player['wins']}
💀 Поражений: {player['losses']}
🎒 Предметов: {len(player['items'])}
💎 Достижений: {len(player['achievements'])}
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_inventory(message, player):
    if not player['items']:
        text = "🎒 **Инвентарь пуст**\n\nСражайся и покупай в магазине!"
    else:
        text = f"🎒 **Инвентарь** ({len(player['items'])} предметов)\n\n"
        for item_id, count in player['inventory'].items():
            if count > 0:
                item = next((i for i in get_shop_items() if i['id'] == item_id), None)
                if item:
                    text += f"{item['emoji']} {item['name']} x{count}\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_leaderboard(message):
    users = db.get_all_users()
    text = "🏆 **Таблица лидеров**\n\n"
    # Сортируем по уровню и звёздам
    sorted_players = sorted(
        player_cache.items(),
        key=lambda x: (x[1][0]['level'], x[1][0]['stars']),
        reverse=True
    )[:10]
    
    medals = ['🥇', '🥈', '🥉']
    for i, (uid, (player, _)) in enumerate(sorted_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} **{player['username'] or 'Аноним'}** — ⭐{player['level']}, 🌟{player['stars']} звёзд\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_achievements(message, player):
    text = "💎 **Достижения**\n\n"
    
    unlocked = player.get('achievements', [])
    
    for key, ach in ACHIEVEMENTS.items():
        if ach['name'] in unlocked:
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
• Достижения (+5-50⭐)
• Ежедневные награды (+2-5⭐)
• Продажа предметов
• Участие в событиях

💰 **Золото можно обменять на звёзды:**
100 золота = 1 звезда
"""
    keyboard = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("🔄 Обменять золото", callback_data="exchange_gold")
    keyboard.add(btn)
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)

def daily_reward(message, player):
    today = datetime.now().date()
    last_daily = player.get('last_daily')
    
    if last_daily and datetime.fromisoformat(last_daily).date() == today:
        bot.send_message(message.chat.id, "🎁 **Сегодня уже получал!**\nПриходи завтра!", parse_mode='Markdown')
        return
    
    reward_gold = random.randint(20, 50)
    reward_stars = random.randint(1, 3)
    
    player['gold'] += reward_gold
    player['stars'] += reward_stars
    player['last_daily'] = datetime.now().isoformat()
    save_player(message.from_user.id, player)
    
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

def battle_start(message, player):
    if player['in_battle']:
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
    save_player(message.from_user.id, player)
    
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
