import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime, timedelta
import random
import asyncio
import sys

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN')  # Для Render используйте переменные окружения
ADMIN_IDS = [int(id) for id in os.environ.get('ADMIN_IDS', '123456789').split(',')]

# Игровые константы
MAX_LEVEL = 100
EXP_PER_LEVEL = 100
START_MONEY = 1000
START_ENERGY = 100
MAX_ENERGY = 100
ENERGY_RESTORE_RATE = 5  # Восстановление энергии в минуту

# === ИГРОВАЯ БАЗА ДАННЫХ ===

class GameDatabase:
    def __init__(self, filename='game_data.json'):
        self.filename = filename
        self.data = self.load_data()
        self.last_save = datetime.now()
    
    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.get_default_data()
        return self.get_default_data()
    
    def get_default_data(self):
        return {
            'players': {},
            'guilds': {},
            'shop': {
                'weapons': {
                    'Меч': {'damage': 10, 'price': 500, 'level': 1},
                    'Лук': {'damage': 15, 'price': 1000, 'level': 3},
                    'Магический посох': {'damage': 25, 'price': 2500, 'level': 5},
                    'Драконий меч': {'damage': 40, 'price': 5000, 'level': 8},
                    'Легендарный меч': {'damage': 60, 'price': 10000, 'level': 12}
                },
                'armor': {
                    'Кожаная броня': {'defense': 10, 'price': 300, 'level': 1},
                    'Стальная броня': {'defense': 20, 'price': 800, 'level': 3},
                    'Мифриловая броня': {'defense': 35, 'price': 2000, 'level': 6},
                    'Драконья броня': {'defense': 50, 'price': 5000, 'level': 10}
                },
                'potions': {
                    'Малое зелье': {'heal': 30, 'price': 100, 'level': 1},
                    'Среднее зелье': {'heal': 60, 'price': 250, 'level': 3},
                    'Большое зелье': {'heal': 100, 'price': 500, 'level': 5},
                    'Эликсир здоровья': {'heal': 200, 'price': 1200, 'level': 8}
                }
            },
            'dungeons': {
                'Лесной лабиринт': {'level': 1, 'reward': [100, 300], 'exp': 20},
                'Пещера гоблинов': {'level': 3, 'reward': [300, 600], 'exp': 40},
                'Подземелье некроманта': {'level': 5, 'reward': [500, 1000], 'exp': 60},
                'Логово дракона': {'level': 8, 'reward': [1000, 2000], 'exp': 100},
                'Цитадель тьмы': {'level': 12, 'reward': [2000, 5000], 'exp': 150}
            },
            'top_players': [],
            'global_events': [],
            'total_players': 0
        }
    
    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            self.last_save = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            return False
    
    def create_player(self, user_id, username):
        if self.get_player_by_user(user_id):
            return None
        
        player_id = f"P-{len(self.data['players'])+1:04d}"
        self.data['players'][player_id] = {
            'user_id': user_id,
            'username': username,
            'level': 1,
            'exp': 0,
            'money': START_MONEY,
            'bank': 0,
            'energy': START_ENERGY,
            'health': 100,
            'max_health': 100,
            'strength': 5,
            'agility': 5,
            'intelligence': 5,
            'luck': 5,
            'guild': None,
            'title': 'Путешественник',
            'weapon': None,
            'armor': None,
            'inventory': [],
            'wins': 0,
            'losses': 0,
            'kills': 0,
            'created_at': datetime.now().isoformat(),
            'last_energy_restore': datetime.now().isoformat(),
            'daily_bonus': None,
            'last_dungeon': None,
            'quests': {
                'active': [],
                'completed': []
            },
            'achievements': []
        }
        self.data['total_players'] += 1
        self.save_data()
        return player_id
    
    def get_player_by_user(self, user_id):
        for pid, player in self.data['players'].items():
            if player['user_id'] == user_id:
                return pid, player
        return None, None
    
    def get_player(self, player_id):
        return self.data['players'].get(player_id)
    
    def add_exp(self, player_id, exp):
        player = self.get_player(player_id)
        if not player:
            return False
        
        player['exp'] += exp
        leveled_up = False
        
        while player['exp'] >= EXP_PER_LEVEL and player['level'] < MAX_LEVEL:
            player['level'] += 1
            player['exp'] -= EXP_PER_LEVEL
            player['strength'] += random.randint(1, 3)
            player['agility'] += random.randint(1, 3)
            player['intelligence'] += random.randint(1, 3)
            player['luck'] += random.randint(0, 2)
            player['max_health'] += 10
            player['health'] = min(player['health'] + 10, player['max_health'])
            leveled_up = True
            
            # Проверка достижений
            self.check_achievements(player_id)
        
        self.save_data()
        return leveled_up
    
    def check_achievements(self, player_id):
        player = self.get_player(player_id)
        if not player:
            return
        
        achievements = []
        if player['level'] >= 10:
            achievements.append('Начинающий герой')
        if player['level'] >= 25:
            achievements.append('Опытный воин')
        if player['level'] >= 50:
            achievements.append('Мастер')
        if player['level'] >= 100:
            achievements.append('Легенда')
        if player['money'] >= 10000:
            achievements.append('Богач')
        if player['money'] >= 100000:
            achievements.append('Магнат')
        if player['wins'] >= 10:
            achievements.append('Победитель')
        if player['wins'] >= 50:
            achievements.append('Чемпион')
            
        for ach in achievements:
            if ach not in player['achievements']:
                player['achievements'].append(ach)
    
    def restore_energy(self, player_id):
        player = self.get_player(player_id)
        if not player:
            return
        
        last_restore = datetime.fromisoformat(player['last_energy_restore'])
        now = datetime.now()
        minutes_passed = (now - last_restore).total_seconds() / 60
        restore_amount = int(minutes_passed * ENERGY_RESTORE_RATE)
        
        if restore_amount > 0:
            player['energy'] = min(MAX_ENERGY, player['energy'] + restore_amount)
            player['last_energy_restore'] = now.isoformat()
            self.save_data()
        
        return player['energy']

# === ИНИЦИАЛИЗАЦИЯ ===

db = GameDatabase()

# === ОСНОВНЫЕ ОБРАБОТЧИКИ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Игрок"
    
    pid, player = db.get_player_by_user(user_id)
    if not player:
        pid = db.create_player(user_id, username)
        await update.message.reply_text(
            f"🏰 Добро пожаловать в мир приключений!\n\n"
            f"Ты - {username}, молодой искатель приключений.\n"
            f"💰 Тебе выдали {START_MONEY} золотых.\n"
            f"⚡ У тебя {START_ENERGY} энергии.\n\n"
            f"Используй /help для помощи!"
        )
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(update, Update):
        message = update.message
    else:
        message = update
    
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data='profile'),
         InlineKeyboardButton("⚡ Действия", callback_data='actions')],
        [InlineKeyboardButton("⚔️ Сражения", callback_data='battle'),
         InlineKeyboardButton("🏰 Подземелья", callback_data='dungeon')],
        [InlineKeyboardButton("🏪 Магазин", callback_data='shop'),
         InlineKeyboardButton("🏦 Банк", callback_data='bank')],
        [InlineKeyboardButton("👥 Гильдия", callback_data='guild'),
         InlineKeyboardButton("🏆 Топ", callback_data='top')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats'),
         InlineKeyboardButton("🎁 Ежедневный бонус", callback_data='daily')]
    ]
    
    # Админ-кнопка
    if message.from_user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin')])
    
    await message.reply_text(
        "🏰 Добро пожаловать в игру!\n\n"
        "Выбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === ПРОФИЛЬ ===

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    if not player:
        await query.edit_message_text("❌ Ты не зарегистрирован!")
        return
    
    # Восстановление энергии
    db.restore_energy(pid)
    
    guild_name = "Нет"
    if player['guild']:
        guild = db.data['guilds'].get(player['guild'])
        if guild:
            guild_name = player['guild']
    
    text = f"👤 {player['username']}\n"
    text += f"🆔 {pid}\n"
    text += f"⭐ Уровень: {player['level']}\n"
    text += f"📈 Опыт: {player['exp']}/{EXP_PER_LEVEL}\n"
    text += f"🏷️ Титул: {player['title']}\n"
    text += f"💰 Золото: {player['money']}\n"
    text += f"🏦 В банке: {player['bank']}\n"
    text += f"❤️ Здоровье: {player['health']}/{player['max_health']}\n"
    text += f"⚡ Энергия: {player['energy']}/{MAX_ENERGY}\n\n"
    text += f"💪 Сила: {player['strength']}\n"
    text += f"🏃 Ловкость: {player['agility']}\n"
    text += f"🧠 Интеллект: {player['intelligence']}\n"
    text += f"🍀 Удача: {player['luck']}\n\n"
    text += f"👥 Гильдия: {guild_name}\n"
    text += f"⚔️ Побед: {player['wins']} | Поражений: {player['losses']}\n"
    
    if player['weapon']:
        text += f"🔫 Оружие: {player['weapon']}\n"
    if player['armor']:
        text += f"🛡️ Броня: {player['armor']}\n"
    
    if player['achievements']:
        text += "\n🏅 Достижения:\n"
        text += ", ".join(player['achievements'][:5])
    
    keyboard = [
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# === ДЕЙСТВИЯ ===

async def actions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💪 Тренировка", callback_data='train')],
        [InlineKeyboardButton("🏥 Лечиться", callback_data='heal')],
        [InlineKeyboardButton("⚡ Восстановить энергию", callback_data='restore_energy')],
        [InlineKeyboardButton("💼 Работа", callback_data='work')],
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(
        "⚡ Выбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    if player['energy'] < 10:
        await query.edit_message_text(
            "❌ Недостаточно энергии! (нужно 10)\n"
            "Энергия восстанавливается со временем.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
            ])
        )
        return
    
    player['energy'] -= 10
    stat_boost = random.choice(['strength', 'agility', 'intelligence'])
    boost_amount = random.randint(1, 3)
    player[stat_boost] += boost_amount
    
    stat_names = {
        'strength': 'Сила',
        'agility': 'Ловкость',
        'intelligence': 'Интеллект'
    }
    
    leveled_up = db.add_exp(pid, random.randint(5, 15))
    db.save_data()
    
    text = f"💪 Тренировка прошла успешно!\n\n"
    text += f"📈 +{boost_amount} {stat_names[stat_boost]}\n"
    text += f"📈 +{random.randint(5, 15)} опыта\n"
    text += f"⚡ Осталось энергии: {player['energy']}\n"
    
    if leveled_up:
        text += f"\n🎉 УРОВЕНЬ ПОВЫШЕН! Ты теперь {player['level']} уровня!"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
        ])
    )

async def heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    heal_needed = player['max_health'] - player['health']
    if heal_needed <= 0:
        await query.edit_message_text(
            "❤️ У тебя полное здоровье!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
            ])
        )
        return
    
    cost = heal_needed * 2
    if player['money'] < cost:
        await query.edit_message_text(
            f"❌ Недостаточно золота! Нужно {cost} золотых.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
            ])
        )
        return
    
    player['money'] -= cost
    player['health'] = player['max_health']
    db.save_data()
    
    await query.edit_message_text(
        f"🏥 Ты полностью вылечился!\n"
        f"❤️ Здоровье: {player['health']}/{player['max_health']}\n"
        f"💰 Осталось: {player['money']} золотых",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
        ])
    )

async def restore_energy_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    current_energy = db.restore_energy(pid)
    
    await query.edit_message_text(
        f"⚡ Энергия восстановлена!\n"
        f"Текущая энергия: {current_energy}/{MAX_ENERGY}\n\n"
        f"Энергия автоматически восстанавливается.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
        ])
    )

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    if player['energy'] < 15:
        await query.edit_message_text(
            "❌ Недостаточно энергии! (нужно 15)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
            ])
        )
        return
    
    player['energy'] -= 15
    money_earned = random.randint(50, 200) + player['level'] * 10
    player['money'] += money_earned
    db.add_exp(pid, random.randint(10, 25))
    db.save_data()
    
    await query.edit_message_text(
        f"💼 Ты поработал и заработал {money_earned} золотых!\n"
        f"⚡ Осталось энергии: {player['energy']}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data='actions')]
        ])
    )

# === СРАЖЕНИЯ ===

async def battle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Найти противника", callback_data='battle_find')],
        [InlineKeyboardButton("🏟️ Арена", callback_data='arena')],
        [InlineKeyboardButton("📊 Моя статистика", callback_data='battle_stats')],
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(
        "⚔️ Боевая арена\n\n"
        "Сражайся с другими игроками!\n"
        "Победа приносит золото, опыт и славу!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def battle_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    if player['health'] < 30:
        await query.edit_message_text(
            "❌ У тебя мало здоровья! (нужно 30+)\n"
            "Восстановись в действиях.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='battle')]
            ])
        )
        return
    
    # Поиск противника
    opponents = []
    for opid, opp in db.data['players'].items():
        if opid != pid and opp['health'] > 20 and opp['user_id'] != user_id:
            opponents.append((opid, opp))
    
    if not opponents:
        await query.edit_message_text(
            "❌ Нет доступных противников!\n"
            "Попробуй позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='battle')]
            ])
        )
        return
    
    opp_id, opp = random.choice(opponents)
    
    # Расчет силы
    player_power = (
        player['strength'] * 2 + 
        player['agility'] + 
        player['level'] * 3
    )
    opp_power = (
        opp['strength'] * 2 + 
        opp['agility'] + 
        opp['level'] * 3
    )
    
    # Учет оружия и брони
    if player['weapon']:
        weapon = db.data['shop']['weapons'].get(player['weapon'])
        if weapon:
            player_power += weapon['damage']
    
    if opp['weapon']:
        weapon = db.data['shop']['weapons'].get(opp['weapon'])
        if weapon:
            opp_power += weapon['damage']
    
    # Бой
    player_hit = random.randint(10, 30) + player_power // 5
    opp_hit = random.randint(10, 30) + opp_power // 5
    
    # Результат
    if player_hit > opp_hit:
        # Победа
        win_money = random.randint(100, 500) + player['level'] * 20
        player['money'] += win_money
        player['wins'] += 1
        player['kills'] += 1
        opp['health'] = max(0, opp['health'] - random.randint(10, 30))
        db.add_exp(pid, random.randint(20, 40))
        db.save_data()
        
        text = f"⚔️ ПОБЕДА!\n\n"
        text += f"Ты победил {opp['username']}!\n"
        text += f"💰 +{win_money} золотых\n"
        text += f"📈 +{random.randint(20, 40)} опыта\n"
        text += f"❤️ Твое здоровье: {player['health']}\n"
        text += f"❤️ Здоровье {opp['username']}: {opp['health']}"
        
    else:
        # Поражение
        player['health'] = max(0, player['health'] - random.randint(10, 25))
        player['losses'] += 1
        opp['wins'] += 1
        db.save_data()
        
        text = f"💀 ПОРАЖЕНИЕ!\n\n"
        text += f"{opp['username']} победил тебя!\n"
        text += f"❤️ Твое здоровье: {player['health']}/{player['max_health']}\n"
        text += f"❤️ Здоровье {opp['username']}: {opp['health']}"
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Еще бой", callback_data='battle_find')],
        [InlineKeyboardButton("🔙 В меню", callback_data='battle')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def battle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    total_fights = player['wins'] + player['losses']
    win_rate = (player['wins'] / total_fights * 100) if total_fights > 0 else 0
    
    text = f"📊 Боевая статистика\n\n"
    text += f"⚔️ Всего боев: {total_fights}\n"
    text += f"🏆 Побед: {player['wins']}\n"
    text += f"💀 Поражений: {player['losses']}\n"
    text += f"🔫 Убийств: {player['kills']}\n"
    text += f"📈 Процент побед: {win_rate:.1f}%\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data='battle')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# === ПОДЗЕМЕЛЬЯ ===

async def dungeon_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for name, dungeon in db.data['dungeons'].items():
        keyboard.append([InlineKeyboardButton(
            f"🏰 {name} (Ур. {dungeon['level']}+)",
            callback_data=f"dungeon_{name}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='menu')])
    
    await query.edit_message_text(
        "🏰 Выбери подземелье:\n\n"
        "Чем выше уровень, тем больше награда!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def dungeon_enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    dungeon_name = query.data.replace('dungeon_', '')
    dungeon = db.data['dungeons'].get(dungeon_name)
    
    if not dungeon:
        return
    
    if player['level'] < dungeon['level']:
        await query.edit_message_text(
            f"❌ Твой уровень слишком низок! Нужно {dungeon['level']} уровень.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='dungeon')]
            ])
        )
        return
    
    if player['energy'] < 20:
        await query.edit_message_text(
            "❌ Недостаточно энергии! (нужно 20)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='dungeon')]
            ])
        )
        return
    
    player['energy'] -= 20
    
    # Шанс успеха зависит от удачи
    success_chance = 70 + player['luck'] * 2
    success = random.random() * 100 < success_chance
    
    if success:
        reward = random.randint(dungeon['reward'][0], dungeon['reward'][1])
        player['money'] += reward
        exp_reward = dungeon['exp'] + random.randint(-10, 20)
        db.add_exp(pid, exp_reward)
        
        # Шанс найти предмет
        if random.random() < 0.2:
            # Случайный предмет
            item_type = random.choice(['weapons', 'armor', 'potions'])
            items = db.data['shop'][item_type]
            if items:
                item_name = random.choice(list(items.keys()))
                if item_name not in player['inventory']:
                    player['inventory'].append(item_name)
                    item_found = f"\n🎁 Ты нашел {item_name}!"
                else:
                    item_found = ""
            else:
                item_found = ""
        else:
            item_found = ""
        
        db.save_data()
        
        text = f"🏰 {dungeon_name} пройдено!\n\n"
        text += f"💰 +{reward} золотых\n"
        text += f"📈 +{exp_reward} опыта{item_found}\n"
        text += f"⚡ Осталось энергии: {player['energy']}"
        
    else:
        # Провал
        damage = random.randint(20, 50)
        player['health'] = max(0, player['health'] - damage)
        db.save_data()
        
        text = f"💀 Провал в {dungeon_name}!\n\n"
        text += f"Монстры одолели тебя!\n"
        text += f"❤️ Потеряно здоровья: {damage}\n"
        text += f"❤️ Осталось: {player['health']}/{player['max_health']}"
    
    keyboard = [
        [InlineKeyboardButton("🏰 Еще подземелье", callback_data='dungeon')],
        [InlineKeyboardButton("🔙 В меню", callback_data='menu')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# === МАГАЗИН ===

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔫 Оружие", callback_data='shop_weapons')],
        [InlineKeyboardButton("🛡️ Броня", callback_data='shop_armor')],
        [InlineKeyboardButton("🧪 Зелья", callback_data='shop_potions')],
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(
        "🏪 Магазин\n\n"
        "Выбери категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def shop_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    category = query.data.replace('shop_', '')
    items = db.data['shop'].get(category)
    
    if not items:
        return
    
    text = f"🛒 {category.capitalize()}:\n\n"
    keyboard = []
    
    for item_name, item_data in items.items():
        if player['level'] >= item_data['level']:
            text += f"• {item_name}\n"
            if 'damage' in item_data:
                text += f"  ⚔️ Урон: {item_data['damage']}\n"
            if 'defense' in item_data:
                text += f"  🛡️ Защита: {item_data['defense']}\n"
            if 'heal' in item_data:
                text += f"  ❤️ Лечение: {item_data['heal']}\n"
            text += f"  💰 Цена: {item_data['price']} золотых\n"
            text += f"  📊 Треб. уровень: {item_data['level']}\n\n"
            keyboard.append([InlineKeyboardButton(
                f"Купить {item_name}",
                callback_data=f"buy_{category}_{item_name}"
            )])
    
    if not keyboard:
        text = "❌ Нет доступных предметов для твоего уровня."
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='shop')])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    _, category, item_name = query.data.split('_', 2)
    item_data = db.data['shop'][category].get(item_name)
    
    if not item_data:
        return
    
    if player['money'] < item_data['price']:
        await query.edit_message_text(
            f"❌ Недостаточно золота! Нужно {item_data['price']} золотых.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data=f'shop_{category}')]
            ])
        )
        return
    
    player['money'] -= item_data['price']
    
    if category == 'weapons':
        player['weapon'] = item_name
    elif category == 'armor':
        player['armor'] = item_name
    elif category == 'potions':
        # Лечение
        heal_amount = item_data['heal']
        player['health'] = min(player['max_health'], player['health'] + heal_amount)
    
    db.save_data()
    
    await query.edit_message_text(
        f"✅ Куплено: {item_name}!\n"
        f"💰 Осталось: {player['money']} золотых",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 В магазин", callback_data='shop')]
        ])
    )

# === БАНК ===

async def bank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💰 Положить", callback_data='bank_deposit')],
        [InlineKeyboardButton("💳 Снять", callback_data='bank_withdraw')],
        [InlineKeyboardButton("📊 Баланс", callback_data='bank_balance')],
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(
        f"🏦 Банк\n\n"
        f"💰 В кармане: {player['money']} золотых\n"
        f"🏦 В банке: {player['bank']} золотых\n"
        f"📈 Процент: 5% в день",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def bank_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['bank_action'] = 'deposit'
    
    await query.edit_message_text(
        "💳 Введи сумму для пополнения:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='bank')]
        ])
    )

async def bank_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['bank_action'] = 'withdraw'
    
    await query.edit_message_text(
        "💳 Введи сумму для снятия:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='bank')]
        ])
    )

async def bank_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    await query.edit_message_text(
        f"🏦 Банковский баланс\n\n"
        f"💰 В кармане: {player['money']} золотых\n"
        f"🏦 В банке: {player['bank']} золотых\n"
        f"📈 Процент: 5% в день\n"
        f"💹 Завтра будет: {int(player['bank'] * 1.05)} золотых",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data='bank')]
        ])
    )

# === ЕЖЕДНЕВНЫЙ БОНУС ===

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    today = datetime.now().date().isoformat()
    if player['daily_bonus'] == today:
        await query.edit_message_text(
            "❌ Ты уже получил ежедневный бонус!\n"
            "Возвращайся завтра!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
            ])
        )
        return
    
    bonus = random.randint(200, 1000) + player['level'] * 50
    player['money'] += bonus
    player['daily_bonus'] = today
    db.add_exp(pid, random.randint(10, 30))
    db.save_data()
    
    await query.edit_message_text(
        f"🎁 Ежедневный бонус!\n\n"
        f"💰 +{bonus} золотых\n"
        f"📈 +{random.randint(10, 30)} опыта\n"
        f"Баланс: {player['money']} золотых",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')]
        ])
    )

# === ТОП ===

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    players = db.data['players'].values()
    sorted_by_level = sorted(players, key=lambda x: x['level'], reverse=True)[:10]
    sorted_by_money = sorted(players, key=lambda x: x['money'], reverse=True)[:10]
    
    text = "🏆 ТОП ИГРОКОВ\n\n"
    text += "⭐ По уровню:\n"
    for i, player in enumerate(sorted_by_level, 1):
        text += f"{i}. {player['username']} - Ур. {player['level']}\n"
    
    text += "\n💰 По богатству:\n"
    for i, player in enumerate(sorted_by_money, 1):
        text += f"{i}. {player['username']} - {player['money']} золотых\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# === СТАТИСТИКА ===

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    players = db.data['players']
    total_players = len(players)
    total_guilds = len(db.data['guilds'])
    total_money = sum(p['money'] + p['bank'] for p in players.values())
    avg_level = sum(p['level'] for p in players.values()) // total_players if total_players > 0 else 0
    
    text = "📊 Статистика сервера\n\n"
    text += f"👥 Игроков: {total_players}\n"
    text += f"👥 Гильдий: {total_guilds}\n"
    text += f"💰 Всего золота: {total_money}\n"
    text += f"📈 Средний уровень: {avg_level}\n"
    text += f"⚔️ Всего боев: {sum(p['wins'] + p['losses'] for p in players.values())}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# === ГИЛЬДИЯ ===

async def guild_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    if player['guild']:
        guild = db.data['guilds'].get(player['guild'])
        if guild:
            text = f"👥 Гильдия: {player['guild']}\n"
            text += f"👑 Лидер: {guild['leader']}\n"
            text += f"👥 Участников: {len(guild['members'])}\n"
            text += f"💰 Казна: {guild['balance']} золотых\n"
            text += f"📈 Уровень гильдии: {guild['level']}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("👤 Участники", callback_data='guild_members')],
                [InlineKeyboardButton("💰 Внести в казну", callback_data='guild_deposit')],
                [InlineKeyboardButton("💀 Покинуть гильдию", callback_data='guild_leave')],
                [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
            ]
            
            if pid == guild['leader']:
                keyboard.insert(1, [InlineKeyboardButton("📢 Объявление", callback_data='guild_announce')])
                keyboard.insert(2, [InlineKeyboardButton("🤝 Пригласить", callback_data='guild_invite')])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Создать гильдию", callback_data='guild_create')],
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(
        "👥 Ты не в гильдии!\n\n"
        "Создай свою гильдию!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def guild_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['guild_create'] = True
    
    await query.edit_message_text(
        "Введи название гильдии:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='guild')]
        ])
    )

async def guild_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    if not player['guild']:
        return
    
    guild = db.data['guilds'].get(player['guild'])
    if not guild:
        return
    
    text = f"👥 Участники гильдии {player['guild']}:\n\n"
    for member_id in guild['members']:
        member = db.get_player(member_id)
        if member:
            role = "👑" if member_id == guild['leader'] else "👤"
            text += f"{role} {member['username']} (Ур. {member['level']})\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data='guild')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# === АДМИН-ПАНЕЛЬ ===

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("❌ Доступ запрещен!")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Выдать золото", callback_data='admin_money')],
        [InlineKeyboardButton("⭐ Выдать уровень", callback_data='admin_level')],
        [InlineKeyboardButton("🏆 Выдать достижение", callback_data='admin_achievement')],
        [InlineKeyboardButton("📢 Объявление", callback_data='admin_announce')],
        [InlineKeyboardButton("📊 Полная статистика", callback_data='admin_full_stats')],
        [InlineKeyboardButton("💾 Сохранить данные", callback_data='admin_save')],
        [InlineKeyboardButton("🔙 Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(
        "👑 Админ-панель",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_full_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        return
    
    players = db.data['players']
    
    text = "📊 Полная статистика\n\n"
    text += f"👥 Игроков: {len(players)}\n"
    text += f"👥 Гильдий: {len(db.data['guilds'])}\n"
    
    total_money = sum(p['money'] + p['bank'] for p in players.values())
    text += f"💰 Всего золота: {total_money}\n"
    
    avg_level = sum(p['level'] for p in players.values()) // len(players) if players else 0
    text += f"📈 Средний уровень: {avg_level}\n\n"
    
    text += "Последние игроки:\n"
    for pid, player in list(players.items())[-5:]:
        text += f"{pid} - {player['username']} (Ур. {player['level']})\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        return
    
    if db.save_data():
        await query.edit_message_text("✅ Данные сохранены успешно!")
    else:
        await query.edit_message_text("❌ Ошибка сохранения!")

# === ОБРАБОТЧИК ТЕКСТА ===

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Создание гильдии
    if context.user_data.get('guild_create'):
        guild_name = text.strip()
        pid, player = db.get_player_by_user(user_id)
        
        if guild_name in db.data['guilds']:
            await update.message.reply_text("❌ Гильдия с таким названием уже существует!")
            return
        
        db.data['guilds'][guild_name] = {
            'leader': pid,
            'members': [pid],
            'balance': 0,
            'level': 1,
            'created_at': datetime.now().isoformat()
        }
        player['guild'] = guild_name
        db.save_data()
        
        await update.message.reply_text(
            f"✅ Гильдия '{guild_name}' создана!\n"
            f"Ты стал лидером!"
        )
        context.user_data['guild_create'] = False
        return
    
    # Банковские операции
    if context.user_data.get('bank_action'):
        try:
            amount = int(text)
            pid, player = db.get_player_by_user(user_id)
            
            if context.user_data['bank_action'] == 'deposit':
                if player['money'] >= amount:
                    player['money'] -= amount
                    player['bank'] += amount
                    db.save_data()
                    await update.message.reply_text(
                        f"✅ Пополнено {amount} золотых\n"
                        f"💰 В кармане: {player['money']}\n"
                        f"🏦 В банке: {player['bank']}"
                    )
                else:
                    await update.message.reply_text("❌ Недостаточно золота!")
            
            elif context.user_data['bank_action'] == 'withdraw':
                if player['bank'] >= amount:
                    player['money'] += amount
                    player['bank'] -= amount
                    db.save_data()
                    await update.message.reply_text(
                        f"✅ Снято {amount} золотых\n"
                        f"💰 В кармане: {player['money']}\n"
                        f"🏦 В банке: {player['bank']}"
                    )
                else:
                    await update.message.reply_text("❌ Недостаточно в банке!")
            
            context.user_data['bank_action'] = None
            
        except ValueError:
            await update.message.reply_text("❌ Введи число!")
        return
    
    # Админские команды
    if user_id in ADMIN_IDS and context.user_data.get('admin_action'):
        parts = text.split()
        if len(parts) == 2:
            target_id = parts[0]
            value = int(parts[1])
            
            target_player = None
            target_pid = None
            for pid, player in db.data['players'].items():
                if pid == target_id or player['username'] == target_id:
                    target_player = player
                    target_pid = pid
                    break
            
            if target_player:
                if context.user_data['admin_action'] == 'money':
                    target_player['money'] += value
                    await update.message.reply_text(
                        f"✅ Выдано {value} золотых {target_player['username']}"
                    )
                elif context.user_data['admin_action'] == 'level':
                    target_player['level'] = value
                    await update.message.reply_text(
                        f"✅ Установлен уровень {value} для {target_player['username']}"
                    )
                elif context.user_data['admin_action'] == 'achievement':
                    if value not in target_player['achievements']:
                        target_player['achievements'].append(text.split(maxsplit=1)[1] if len(text.split()) > 2 else "Герой")
                    await update.message.reply_text(
                        f"✅ Достижение добавлено {target_player['username']}"
                    )
                db.save_data()
            else:
                await update.message.reply_text("❌ Игрок не найден!")
            
            context.user_data['admin_action'] = None
        else:
            await update.message.reply_text("❌ Используй: ID_игрока Значение")
        return
    
    if context.user_data.get('admin_announce'):
        # Глобальное объявление
        for pid, player in db.data['players'].items():
            try:
                await context.bot.send_message(
                    chat_id=player['user_id'],
                    text=f"📢 ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАЦИИ:\n\n{text}"
                )
            except:
                pass
        
        await update.message.reply_text("✅ Объявление отправлено всем игрокам!")
        context.user_data['admin_announce'] = False
        return
    
    # Если просто текст
    await update.message.reply_text(
        "Используй кнопки для навигации",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Главное меню", callback_data='menu')]
        ])
    )

# === ГЛАВНЫЙ ОБРАБОТЧИК КНОПОК ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Навигация
    if data == 'menu':
        await show_main_menu(update, context)
        return
    
    # Словарь обработчиков
    handlers = {
        'profile': profile,
        'actions': actions_menu,
        'battle': battle_menu,
        'dungeon': dungeon_menu,
        'shop': shop_menu,
        'bank': bank_menu,
        'guild': guild_menu,
        'top': show_top,
        'stats': show_stats,
        'daily': daily_bonus,
        'admin': admin_panel,
        'admin_full_stats': admin_full_stats,
        'admin_save': admin_save,
        'train': train,
        'heal': heal,
        'restore_energy': restore_energy_action,
        'work': work,
        'battle_find': battle_find,
        'battle_stats': battle_stats,
        'bank_deposit': bank_deposit,
        'bank_withdraw': bank_withdraw,
        'bank_balance': bank_balance,
        'guild_create': guild_create,
        'guild_members': guild_members,
        'guild_deposit': guild_deposit,
        'guild_leave': guild_leave,
        'guild_announce': guild_announce,
        'guild_invite': guild_invite,
        'admin_money': admin_money,
        'admin_level': admin_level,
        'admin_achievement': admin_achievement,
        'admin_announce': admin_announce,
    }
    
    # Подземелья
    if data.startswith('dungeon_'):
        await dungeon_enter(update, context)
        return
    
    # Магазин
    if data.startswith('shop_'):
        if data == 'shop':
            await shop_menu(update, context)
        else:
            await shop_category(update, context)
        return
    
    # Покупка
    if data.startswith('buy_'):
        await buy_item(update, context)
        return
    
    # Вызов обработчика
    handler = handlers.get(data)
    if handler:
        await handler(update, context)

# === ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ===

async def guild_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['guild_deposit'] = True
    
    await query.edit_message_text(
        "Введи сумму для внесения в казну гильдии:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='guild')]
        ])
    )

async def guild_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pid, player = db.get_player_by_user(user_id)
    
    if not player['guild']:
        await query.edit_message_text("❌ Ты не в гильдии!")
        return
    
    guild = db.data['guilds'].get(player['guild'])
    if guild:
        if pid == guild['leader']:
            await query.edit_message_text("❌ Лидер не может покинуть гильдию!\nСначала передай лидерство.")
            return
        guild['members'].remove(pid)
    
    player['guild'] = None
    db.save_data()
    
    await query.edit_message_text(
        "💀 Ты покинул гильдию!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 В меню", callback_data='menu')]
        ])
    )

async def guild_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['guild_announce'] = True
    
    await query.edit_message_text(
        "Введи объявление для гильдии:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='guild')]
        ])
    )

async def guild_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['guild_invite'] = True
    
    await query.edit_message_text(
        "Введи ID игрока для приглашения:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='guild')]
        ])
    )

async def admin_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['admin_action'] = 'money'
    
    await query.edit_message_text(
        "Введи ID игрока и сумму через пробел:\nПример: P-0001 50000",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='admin')]
        ])
    )

async def admin_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['admin_action'] = 'level'
    
    await query.edit_message_text(
        "Введи ID игрока и уровень через пробел:\nПример: P-0001 10",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='admin')]
        ])
    )

async def admin_achievement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['admin_action'] = 'achievement'
    
    await query.edit_message_text(
        "Введи ID игрока и достижение через пробел:\nПример: P-0001 Легендарный герой",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='admin')]
        ])
    )

async def admin_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['admin_announce'] = True
    
    await query.edit_message_text(
        "Введи текст объявления:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data='admin')]
        ])
    )

# === КОМАНДА ПОМОЩИ ===

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🏰 BEST RUSSIA - Помощь

/start - Главное меню
/help - Эта справка

⚡ Основные механики:

👤 Профиль - твой персонаж
⚡ Действия - тренировка, лечение, работа
⚔️ Сражения - PvP с другими игроками
🏰 Подземелья - PvE приключения
🏪 Магазин - покупка оружия и брони
🏦 Банк - хранение золота с процентами
👥 Гильдия - создание/управление гильдией
🎁 Ежедневный бонус - каждый день

📈 Система развития:
- Тренировки повышают характеристики
- Битвы приносят опыт и золото
- Уровень открывает новое снаряжение
- Достижения за особые успехи

Удачи в приключениях! 🎮"""

    await update.message.reply_text(text)

# === ЗАПУСК ===

async def main():  # <--- ОБЯЗАТЕЛЬНО добавьте async здесь
    """Запуск Бота"""
    application = Application.builder().token(TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Текст
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск
    print("🚀 Игровой бот BEST RUSSIA запущен!")
    print(f"👑 Администраторы: {ADMIN_IDS}")
    print(f"📁 Файл данных: {db.filename}")
    print(f"⚡ Энергия восстанавливается: {ENERGY_RESTORE_RATE} единиц/минуту")

    # Инициализация и запуск
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Держим бота активным
    try:
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    import asyncio
    try:
        # Запускаем асинхронную main() через asyncio.run() - это правильно и безопасно
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
