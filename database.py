# database.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# ============================================
# === ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ===
# ============================================

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost:5432/battlez')

def get_db_connection():
    """Подключение к PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)

def get_db_cursor():
    """Подключение с курсором для dict"""
    conn = get_db_connection()
    return conn, conn.cursor(cursor_factory=RealDictCursor)

# ============================================
# === РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ===
# ============================================

def get_user_by_username(username):
    """Получить пользователя по username"""
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    """Получить пользователя по email"""
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(username, email, password_hash):
    """Создать нового пользователя"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (username, email, password_hash, joined, avatar)
        VALUES (%s, %s, %s, NOW(), %s)
    ''', (username, email, password_hash, '👤'))
    conn.commit()
    conn.close()

def verify_user(username):
    """Верифицировать пользователя"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET verified = TRUE WHERE username = %s', (username,))
    conn.commit()
    conn.close()

def unverify_user(username):
    """Отозвать верификацию"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET verified = FALSE WHERE username = %s', (username,))
    conn.commit()
    conn.close()

def get_all_users():
    """Получить всех пользователей"""
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT username, email, verified, joined FROM users ORDER BY joined DESC')
    users = c.fetchall()
    conn.close()
    return users

def get_user_stats():
    """Получить статистику пользователей"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE verified = TRUE')
    verified = c.fetchone()[0]
    conn.close()
    return total, verified

# ============================================
# === РАБОТА С КОДАМИ ПОДТВЕРЖДЕНИЯ ===
# ============================================

def save_verification_code(email, username, code):
    """Сохранить код подтверждения"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO verification_codes (email, username, code, expires_at)
        VALUES (%s, %s, %s, NOW() + INTERVAL '5 minutes')
    ''', (email, username, code))
    conn.commit()
    conn.close()

def check_verification_code(code, email):
    """Проверить код подтверждения"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT * FROM verification_codes 
        WHERE code = %s AND email = %s AND used = FALSE AND expires_at > NOW()
    ''', (code, email))
    result = c.fetchone()
    if result:
        c.execute('UPDATE verification_codes SET used = TRUE WHERE code = %s', (code,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# ============================================
# === РАБОТА С TELEGRAM-ПОЛЬЗОВАТЕЛЯМИ ===
# ============================================

def get_telegram_user(telegram_id):
    """Получить пользователя бота по Telegram ID"""
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT * FROM telegram_users WHERE telegram_id = %s', (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user

def register_telegram_user(telegram_id, username, first_name, last_name):
    """Зарегистрировать пользователя в боте"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO telegram_users (telegram_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name
    ''', (telegram_id, username, first_name, last_name))
    conn.commit()
    conn.close()

def get_all_telegram_users():
    """Получить всех пользователей бота"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT telegram_id FROM telegram_users')
    users = c.fetchall()
    conn.close()
    return users

# ============================================
# === РАБОТА С УВЕДОМЛЕНИЯМИ ===
# ============================================

def save_notification(message):
    """Сохранить уведомление в БД"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO notifications (message) VALUES (%s)', (message,))
    conn.commit()
    conn.close()

def get_notifications(limit=10):
    """Получить последние уведомления"""
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT * FROM notifications ORDER BY sent_at DESC LIMIT %s', (limit,))
    notifications = c.fetchall()
    conn.close()
    return notifications
