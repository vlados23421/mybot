# database.py
import os
import psycopg
from psycopg.rows import dict_row

# ============================================
# === ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ===
# ============================================

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Подключение к PostgreSQL"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL не найден в переменных окружения!")
    return psycopg.connect(DATABASE_URL)

# ============================================
# === ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ===
# ============================================

def init_db():
    """Создание всех таблиц, если их нет"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Таблица пользователей сайта
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                verified BOOLEAN DEFAULT FALSE,
                joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                avatar VARCHAR(10) DEFAULT '👤',
                email_verified BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Таблица Telegram-пользователей
        cur.execute('''
            CREATE TABLE IF NOT EXISTS telegram_users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Таблица кодов подтверждения
        cur.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                id SERIAL PRIMARY KEY,
                code VARCHAR(6) NOT NULL,
                email VARCHAR(100) NOT NULL,
                username VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                used BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Таблица уведомлений
        cur.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                message TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_to INTEGER
            )
        ''')
        
        conn.commit()
        print('✅ Все таблицы созданы/проверены!')
    conn.close()

# ============================================
# === ПОЛЬЗОВАТЕЛИ САЙТА ===
# ============================================

def get_user_by_username(username):
    """Получить пользователя по username"""
    conn = get_db_connection()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    """Получить пользователя по email"""
    conn = get_db_connection()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
    conn.close()
    return user

def get_all_users():
    """Получить всех пользователей"""
    conn = get_db_connection()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute('SELECT username, email, verified, joined FROM users ORDER BY joined DESC')
        users = cur.fetchall()
    conn.close()
    return users

def get_user_stats():
    """Получить статистику пользователей"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM users')
        total = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM users WHERE verified = TRUE')
        verified = cur.fetchone()[0]
    conn.close()
    return total, verified

def verify_user(username):
    """Верифицировать пользователя"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('UPDATE users SET verified = TRUE WHERE username = %s', (username,))
    conn.commit()
    conn.close()

def unverify_user(username):
    """Отозвать верификацию"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('UPDATE users SET verified = FALSE WHERE username = %s', (username,))
    conn.commit()
    conn.close()

# ============================================
# === ПОЛЬЗОВАТЕЛИ TELEGRAM ===
# ============================================

def get_telegram_user(telegram_id):
    """Получить пользователя бота по Telegram ID"""
    conn = get_db_connection()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute('SELECT * FROM telegram_users WHERE telegram_id = %s', (telegram_id,))
        user = cur.fetchone()
    conn.close()
    return user

def register_telegram_user(telegram_id, username, first_name, last_name):
    """Зарегистрировать пользователя в боте"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO telegram_users (telegram_id, username, first_name, last_name, registered_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                registered_at = NOW()
        ''', (telegram_id, username, first_name, last_name))
    conn.commit()
    conn.close()

def get_all_telegram_users():
    """Получить всех пользователей бота"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT telegram_id FROM telegram_users')
        users = cur.fetchall()
    conn.close()
    return users

def delete_telegram_user(telegram_id):
    """Удалить пользователя из бота"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('DELETE FROM telegram_users WHERE telegram_id = %s', (telegram_id,))
    conn.commit()
    conn.close()

# ============================================
# === КОДЫ ПОДТВЕРЖДЕНИЯ ===
# ============================================

def save_verification_code(email, username, code):
    """Сохранить код подтверждения"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO verification_codes (email, username, code, expires_at)
            VALUES (%s, %s, %s, NOW() + INTERVAL '5 minutes')
        ''', (email, username, code))
    conn.commit()
    conn.close()

def check_verification_code(code, email):
    """Проверить код подтверждения"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT * FROM verification_codes 
            WHERE code = %s AND email = %s AND used = FALSE AND expires_at > NOW()
        ''', (code, email))
        result = cur.fetchone()
        if result:
            cur.execute('UPDATE verification_codes SET used = TRUE WHERE code = %s', (code,))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False

# ============================================
# === УВЕДОМЛЕНИЯ ===
# ============================================

def save_notification(message):
    """Сохранить уведомление в БД"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('INSERT INTO notifications (message) VALUES (%s)', (message,))
    conn.commit()
    conn.close()

def get_notifications(limit=10):
    """Получить последние уведомления"""
    conn = get_db_connection()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute('SELECT * FROM notifications ORDER BY sent_at DESC LIMIT %s', (limit,))
        notifications = cur.fetchall()
    conn.close()
    return notifications
