import telebot
from telebot import types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import os
import time
from datetime import datetime
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

# PostgreSQL подключение из переменных окружения Render
DATABASE_URL = os.environ.get("DATABASE_URL")  # Render сам добавит эту переменную

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not BOT_TOKEN or not CHANNEL_ID or not DATABASE_URL:
    logger.error("❌ Ошибка: BOT_TOKEN, CHANNEL_ID или DATABASE_URL не заданы!")
    exit(1)

# ===== ПОДКЛЮЧЕНИЕ К POSTGRESQL =====
class Database:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None
        self.init_pool()
        self.init_tables()

    def init_pool(self):
        """Создает пул соединений с БД"""
        try:
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.db_url
            )
            logger.info("✅ Пул соединений с PostgreSQL создан")
        except Exception as e:
            logger.error(f"❌ Ошибка создания пула: {e}")
            raise

    def get_connection(self):
        """Получает соединение из пула"""
        return self.pool.getconn()

    def return_connection(self, conn):
        """Возвращает соединение в пул"""
        self.pool.putconn(conn)

    def init_tables(self):
        """Создает необходимые таблицы"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Таблица для всех заявок
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS applications (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        user_name VARCHAR(255),
                        app_type VARCHAR(50) NOT NULL,
                        data JSONB NOT NULL,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Таблица для хелперов (отдельно для удобства)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS helpers (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT UNIQUE NOT NULL,
                        name VARCHAR(255),
                        age INTEGER,
                        experience TEXT,
                        contact VARCHAR(255),
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        approved_at TIMESTAMP
                    )
                """)

                # Таблица для жалоб (отдельно)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS complaints (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        against_user VARCHAR(255),
                        reason TEXT,
                        evidence TEXT,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP
                    )
                """)

                # Таблица для обращений в техподдержку
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS support_requests (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        problem TEXT,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP
                    )
                """)

                conn.commit()
                logger.info("✅ Таблицы успешно созданы/проверены")
        except Exception as e:
            logger.error(f"❌ Ошибка создания таблиц: {e}")
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)

    def save_application(self, user_id, app_type, data, user_name=None):
        """Сохраняет заявку в БД"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO applications (user_id, user_name, app_type, data)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (user_id, user_name, app_type, json.dumps(data)))
                
                app_id = cur.fetchone()[0]
                conn.commit()
                
                # Дополнительное сохранение в специфические таблицы
                if app_type == "helper":
                    self.save_helper(user_id, data)
                elif app_type == "complaint":
                    self.save_complaint(user_id, data)
                elif app_type == "support":
                    self.save_support(user_id, data)
                
                logger.info(f"✅ Заявка #{app_id} сохранена в БД")
                return app_id
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения заявки: {e}")
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)

    def save_helper(self, user_id, data):
        """Сохраняет заявку на хелпера в отдельную таблицу"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO helpers (user_id, name, age, experience, contact)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        name = EXCLUDED.name,
                        age = EXCLUDED.age,
                        experience = EXCLUDED.experience,
                        contact = EXCLUDED.contact,
                        status = 'pending',
                        approved_at = NULL
                """, (
                    user_id,
                    data.get('name'),
                    int(data.get('age')) if data.get('age') else None,
                    data.get('experience'),
                    data.get('contact')
                ))
                conn.commit()
                logger.info(f"✅ Заявка на хелпера сохранена для user_id={user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения хелпера: {e}")
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)

    def save_complaint(self, user_id, data):
        """Сохраняет жалобу в отдельную таблицу"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO complaints (user_id, against_user, reason, evidence)
                    VALUES (%s, %s, %s, %s)
                """, (
                    user_id,
                    data.get('against'),
                    data.get('reason'),
                    data.get('evidence')
                ))
                conn.commit()
                logger.info(f"✅ Жалоба сохранена от user_id={user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения жалобы: {e}")
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)

    def save_support(self, user_id, data):
        """Сохраняет обращение в техподдержку"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO support_requests (user_id, problem)
                    VALUES (%s, %s)
                """, (
                    user_id,
                    data.get('text')
                ))
                conn.commit()
                logger.info(f"✅ Обращение в поддержку сохранено от user_id={user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения обращения: {e}")
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)

    def get_all_applications(self, limit=100):
        """Получает последние заявки (для администратора)"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, user_id, user_name, app_type, data, status, created_at
                    FROM applications
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка получения заявок: {e}")
            return []
        finally:
            self.return_connection(conn)

    def update_status(self, app_id, new_status):
        """Обновляет статус заявки"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE applications 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_status, app_id))
                conn.commit()
                logger.info(f"✅ Статус заявки #{app_id} обновлен на {new_status}")
                return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса: {e}")
            conn.rollback()
            return False
        finally:
            self.return_connection(conn)

# ===== ИНИЦИАЛИЗАЦИЯ =====
db = Database(DATABASE_URL)
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(BOT_TOKEN, state_storage=state_storage)

# ===== СОСТОЯНИЯ =====
class UserStates(StatesGroup):
    helper_name = State()
    helper_age = State()
    helper_experience = State()
    helper_contact = State()
    support_problem = State()
    complain_against = State()
    complain_reason = State()
    complain_evidence = State()

# ===== КОМАНДЫ АДМИНИСТРАТОРА =====
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Простая админ-панель (можно расширить)"""
    # Проверка, что пользователь админ (можно задать список ID)
    admin_ids = [123456789, 987654321]  # Замените на свои ID
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⛔ У вас нет прав администратора!")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📋 Последние заявки", callback_data="admin_apps"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    )
    bot.send_message(message.chat.id, "🔐 Админ-панель:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    if call.data == "admin_apps":
        apps = db.get_all_applications(10)
        if not apps:
            bot.edit_message_text("📭 Нет заявок", call.message.chat.id, call.message.message_id)
            return
        
        text = "📋 **Последние заявки:**\n\n"
        for app in apps:
            text += f"#{app['id']} | {app['app_type']} | {app['status']}\n"
            text += f"👤 {app['user_name'] or app['user_id']}\n"
            text += f"⏰ {app['created_at']}\n\n"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    
    elif call.data == "admin_stats":
        # Простая статистика
        text = "📊 **Статистика:**\n\n"
        # Можно добавить запросы для подсчета заявок по типам
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
import json

def send_to_channel(app_type, text, user_id, user_name=None):
    """Отправляет заявку в канал/чат"""
    try:
        header = f"📩 НОВАЯ ЗАЯВКА: {app_type}\n"
        header += f"👤 От: {user_name or user_id}\n"
        header += f"🆔 ID: {user_id}\n"
        header += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        
        bot.send_message(CHANNEL_ID, header + text)
        logger.info(f"✅ Заявка отправлена в канал: {app_type}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в канал: {e}")

# ===== ОСТАЛЬНЫЕ ХЕНДЛЕРЫ (ТЕ ЖЕ, ЧТО И РАНЬШЕ, НО С ИСПОЛЬЗОВАНИЕМ БД) =====

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🙋 Подать заявку на Хелпера")
    btn2 = types.KeyboardButton("🛠 Обратиться в техподдержку")
    btn3 = types.KeyboardButton("⚠️ Подать жалобу")
    btn4 = types.KeyboardButton("🔐 Админ-панель")  # Для админов
    markup.add(btn1, btn2, btn3)
    
    # Если пользователь админ - показываем админ-кнопку
    admin_ids = [123456789, 987654321]  # Замените на свои ID
    if message.from_user.id in admin_ids:
        markup.add(btn4)
    
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в VIBE RUSSIA!\n"
        "Выберите нужный пункт меню:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == "🙋 Подать заявку на Хелпера")
def start_helper(message):
    bot.set_state(message.from_user.id, UserStates.helper_name, message.chat.id)
    bot.send_message(
        message.chat.id,
        "📝 Заполните анкету для вступления в команду Хелперов.\n"
        "Введите ваше Имя и Фамилию:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "🛠 Обратиться в техподдержку")
def start_support(message):
    bot.set_state(message.from_user.id, UserStates.support_problem, message.chat.id)
    bot.send_message(
        message.chat.id,
        "🔧 Опишите вашу проблему как можно подробнее:\n"
        "(Укажите, что именно случилось, и приложите скриншот, если нужно)",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "⚠️ Подать жалобу")
def start_complain(message):
    bot.set_state(message.from_user.id, UserStates.complain_against, message.chat.id)
    bot.send_message(
        message.chat.id,
        "⚠️ Подача жалобы.\n"
        "Укажите ник или ID человека, на которого жалуетесь:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "🔐 Админ-панель")
def admin_button(message):
    admin_panel(message)

# ===== ОБРАБОТКА АНКЕТЫ ХЕЛПЕРА =====
@bot.message_handler(state=UserStates.helper_name)
def process_helper_name(message):
    if message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Заявка отменена.")
        return

    bot.send_message(message.chat.id, "📅 Введите ваш возраст:")
    bot.set_state(message.from_user.id, UserStates.helper_age, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text

@bot.message_handler(state=UserStates.helper_age)
def process_helper_age(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "⛔ Введите возраст цифрами.")
        return

    bot.send_message(message.chat.id, "💬 Расскажите о вашем опыте работы (или почему вы хотите стать Хелпером):")
    bot.set_state(message.from_user.id, UserStates.helper_experience, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['age'] = message.text

@bot.message_handler(state=UserStates.helper_experience)
def process_helper_experience(message):
    bot.send_message(message.chat.id, "📱 Оставьте контакт для связи (Telegram, Discord или номер телефона):")
    bot.set_state(message.from_user.id, UserStates.helper_contact, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['experience'] = message.text

@bot.message_handler(state=UserStates.helper_contact)
def process_helper_contact(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['contact'] = message.text
        
        text = (
            f"👤 Имя: {data.get('name')}\n"
            f"📅 Возраст: {data.get('age')}\n"
            f"💬 Опыт: {data.get('experience')}\n"
            f"📱 Контакт: {data.get('contact')}"
        )
        
        # Сохраняем в БД
        user_name = message.from_user.username or message.from_user.first_name
        db.save_application(
            message.from_user.id,
            "helper",
            data,
            user_name
        )

    send_to_channel("ЗАЯВКА НА ХЕЛПЕРА", text, message.from_user.id, message.from_user.username)

    bot.delete_state(message.from_user.id, message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🙋 Подать заявку на Хелпера"),
        types.KeyboardButton("🛠 Обратиться в техподдержку"),
        types.KeyboardButton("⚠️ Подать жалобу")
    )
    bot.send_message(
        message.chat.id,
        "✅ Ваша заявка отправлена! Мы свяжемся с вами в ближайшее время.",
        reply_markup=markup
    )

# ===== ОБРАБОТКА ТЕХПОДДЕРЖКИ =====
@bot.message_handler(state=UserStates.support_problem, content_types=['text', 'photo', 'document'])
def process_support(message):
    if message.text and message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Отменено.")
        return

    text = "📝 Описание проблемы:\n"
    
    if message.text:
        text += message.text
        problem_text = message.text
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        text = f"🖼 Скриншот: {file_url}\n\n📝 Описание: {message.caption if message.caption else 'Без описания'}"
        problem_text = message.caption if message.caption else "Скриншот"
    elif message.document:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        text = f"📎 Файл: {file_url}\n\n📝 Описание: {message.caption if message.caption else 'Без описания'}"
        problem_text = message.caption if message.caption else "Файл"

    # Сохраняем в БД
    user_name = message.from_user.username or message.from_user.first_name
    db.save_application(
        message.from_user.id,
        "support",
        {"text": problem_text, "full_text": text},
        user_name
    )

    send_to_channel("ОБРАЩЕНИЕ В ТЕХПОДДЕРЖКУ", text, message.from_user.id, message.from_user.username)

    bot.delete_state(message.from_user.id, message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🙋 Подать заявку на Хелпера"),
        types.KeyboardButton("🛠 Обратиться в техподдержку"),
        types.KeyboardButton("⚠️ Подать жалобу")
    )
    bot.send_message(
        message.chat.id,
        "✅ Ваше обращение отправлено! Техподдержка свяжется с вами.",
        reply_markup=markup
    )

# ===== ОБРАБОТКА ЖАЛОБЫ =====
@bot.message_handler(state=UserStates.complain_against)
def process_complain_against(message):
    if message.text.lower() == "/cancel":
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, "❌ Отменено.")
        return

    bot.send_message(message.chat.id, "📝 Опишите причину жалобы (что произошло):")
    bot.set_state(message.from_user.id, UserStates.complain_reason, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['against'] = message.text

@bot.message_handler(state=UserStates.complain_reason)
def process_complain_reason(message):
    bot.send_message(message.chat.id, "📎 Приложите доказательства (скриншоты, ссылки) или напишите 'нет':")
    bot.set_state(message.from_user.id, UserStates.complain_evidence, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['reason'] = message.text

@bot.message_handler(state=UserStates.complain_evidence, content_types=['text', 'photo', 'document'])
def process_complain_evidence(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        evidence = ""

        if message.photo:
            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            evidence = f"🖼 Скриншот: https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        elif message.document:
            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            evidence = f"📎 Файл: https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        else:
            evidence = message.text

        data['evidence'] = evidence
        
        text = (
            f"👤 Жалоба на: {data.get('against')}\n"
            f"📝 Причина: {data.get('reason')}\n"
            f"📎 Доказательства: {evidence}"
        )
        
        # Сохраняем в БД
        user_name = message.from_user.username or message.from_user.first_name
        db.save_application(
            message.from_user.id,
            "complaint",
            data,
            user_name
        )

    send_to_channel("НОВАЯ ЖАЛОБА", text, message.from_user.id, message.from_user.username)

    bot.delete_state(message.from_user.id, message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🙋 Подать заявку на Хелпера"),
        types.KeyboardButton("🛠 Обратиться в техподдержку"),
        types.KeyboardButton("⚠️ Подать жалобу")
    )
    bot.send_message(
        message.chat.id,
        "✅ Жалоба отправлена! Администрация рассмотрит её в ближайшее время.",
        reply_markup=markup
    )

# ===== КОМАНДА /CANCEL =====
@bot.message_handler(commands=['cancel'])
def cancel(message):
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(message.chat.id, "❌ Действие отменено.", reply_markup=types.ReplyKeyboardRemove())

# ===== ОБРАБОТКА ВСЕХ ОСТАЛЬНЫХ СООБЩЕНИЙ =====
@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🙋 Подать заявку на Хелпера"),
        types.KeyboardButton("🛠 Обратиться в техподдержку"),
        types.KeyboardButton("⚠️ Подать жалобу")
    )
    
    admin_ids = [123456789, 987654321]  # Замените на свои ID
    if message.from_user.id in admin_ids:
        markup.add(types.KeyboardButton("🔐 Админ-панель"))
    
    bot.send_message(
        message.chat.id,
        "❗ Используйте кнопки меню или команды /start и /cancel.",
        reply_markup=markup
    )

# ===== ЗАПУСК БОТА =====
if __name__ == "__main__":
    logger.info("🚀 Бот VIBE RUSSIA с PostgreSQL запущен на Render...")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"❌ Ошибка в polling: {e}")
            logger.info("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)
