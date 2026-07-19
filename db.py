import sqlite3
import os

DB_PATH = "medical_bot.db"

def init_db():
    """Ініціалізація бази даних та створення таблиць."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            group_number INTEGER NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procedure_name TEXT NOT NULL,
            group_number INTEGER NOT NULL,
            time_slot TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_type TEXT NOT NULL,
            procedure_name TEXT NOT NULL,
            group_number INTEGER NOT NULL,
            time_slot TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = None):
    """Отримати налаштування за ключем."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    """Зберегти або оновити налаштування."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_user(user_id: int):
    """Отримати інформацію про користувача за його Telegram ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, last_name, group_number, registered_at FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {
            "user_id": user[0],
            "username": user[1],
            "first_name": user[2],
            "last_name": user[3],
            "group_number": user[4],
            "registered_at": user[5]
        }
    return None

def register_user(user_id: int, username: str, first_name: str, last_name: str, group_number: int):
    """Зареєструвати нового користувача або оновити існуючого."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, group_number)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, first_name, last_name, group_number))
    conn.commit()
    conn.close()

def get_users_by_group():
    """Отримати кількість користувачів у кожній групі."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT group_number, COUNT(*) FROM users GROUP BY group_number")
    stats = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in stats}

def get_all_users_grouped():
    """Отримати всіх користувачів, згрупованих за номером групи."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, last_name, group_number FROM users ORDER BY group_number, first_name")
    rows = cursor.fetchall()
    conn.close()

    # Створюємо словник для всіх 8 груп
    groups = {i: [] for i in range(1, 9)}
    for row in rows:
        grp = row[4]
        if grp in groups:
            groups[grp].append({
                "user_id": row[0],
                "username": row[1],
                "first_name": row[2],
                "last_name": row[3]
            })
    return groups

def update_user_group(user_id: int, group_number: int):
    """Оновити групу користувача."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET group_number = ? WHERE user_id = ?", (group_number, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id: int):
    """Видалити користувача з бази даних."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    """Отримати плоский список всіх зареєстрованих користувачів."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, last_name, group_number FROM users ORDER BY group_number, first_name")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "user_id": row[0],
        "username": row[1],
        "first_name": row[2],
        "last_name": row[3],
        "group_number": row[4]
    } for row in rows]

def clear_schedules():
    """Очистити всі записи графіка."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedules")
    conn.commit()
    conn.close()

def add_schedule_entry(procedure_name: str, group_number: int, time_slot: str):
    """Додати новий запис до графіка."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO schedules (procedure_name, group_number, time_slot) VALUES (?, ?, ?)",
        (procedure_name, group_number, time_slot)
    )
    conn.commit()
    conn.close()

def get_schedule_for_group(group_number: int):
    """Отримати розклад процедур для конкретної групи."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, procedure_name, time_slot FROM schedules WHERE group_number = ? ORDER BY time_slot",
        (group_number,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "procedure_name": r[1], "time_slot": r[2]} for r in rows]

def save_template(day_type: str, parsed_entries: list):
    """Очистити старий шаблон та зберегти новий."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM templates WHERE day_type = ?", (day_type,))
    for entry in parsed_entries:
        cursor.execute(
            "INSERT INTO templates (day_type, procedure_name, group_number, time_slot) VALUES (?, ?, ?, ?)",
            (day_type, entry["procedure"], entry["group"], entry["time"])
        )
    conn.commit()
    conn.close()

def clear_template(day_type: str):
    """Видалити шаблон для певного типу дня."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM templates WHERE day_type = ? ", (day_type,))
    conn.commit()
    conn.close()


def apply_template_to_active(day_type: str):
    """Скопіювати шаблон в активний графік."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedules")
    cursor.execute(
        "INSERT INTO schedules (procedure_name, group_number, time_slot) "
        "SELECT procedure_name, group_number, time_slot FROM templates WHERE day_type = ?",
        (day_type,)
    )
    conn.commit()
    conn.close()

def get_active_entry(entry_id: int):
    """Отримати один запис з активного графіка."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, procedure_name, group_number, time_slot FROM schedules WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "procedure_name": row[1], "group_number": row[2], "time_slot": row[3]}
    return None

def update_active_time(entry_id: int, new_time: str):
    """Оновити час активного запису."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE schedules SET time_slot = ? WHERE id = ?", (new_time, entry_id))
    conn.commit()
    conn.close()

def update_active_group(entry_id: int, new_group: int):
    """Оновити групу активного запису."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE schedules SET group_number = ? WHERE id = ?", (new_group, entry_id))
    conn.commit()
    conn.close()

def delete_active_entry(entry_id: int):
    """Видалити активний запис."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedules WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

def get_all_active_procedures():
    """Отримати список всіх унікальних процедур в активному графіку."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT procedure_name FROM schedules ORDER BY procedure_name")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_active_entries_by_procedure(procedure_name: str):
    """Отримати всі записи для певної процедури."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, group_number, time_slot FROM schedules WHERE procedure_name = ? ORDER BY group_number, time_slot", (procedure_name,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "group_number": r[1], "time_slot": r[2]} for r in rows]
