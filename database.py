import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_path: str = "fitness_bot.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        """Возвращает соединение с базой данных"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        """Инициализация базы данных с тестовыми данными"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    name TEXT,
                    phone TEXT,
                    username TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица тренировок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trainings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    max_people INTEGER DEFAULT 10
                )
            ''')

            # Таблица расписания
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    training_id INTEGER,
                    datetime TEXT,
                    available_slots INTEGER,
                    FOREIGN KEY (training_id) REFERENCES trainings (id)
                )
            ''')

            # Таблица записей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    schedule_id INTEGER,
                    status TEXT DEFAULT 'active',
                    booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (schedule_id) REFERENCES schedule (id)
                )
            ''')

            # Добавляем тестовые данные если их нет
            cursor.execute("SELECT COUNT(*) FROM trainings")
            if cursor.fetchone()[0] == 0:
                self._add_sample_data(cursor)

            conn.commit()

    def _add_sample_data(self, cursor):
        """Добавляет тестовые данные"""
        # Тренировки
        trainings = [
            (1, 'Йога для начинающих', 'Утренняя йога для всех уровней', 15),
            (2, 'Силовая тренировка', 'Интенсивная тренировка с весами', 10),
            (3, 'Стретчинг', 'Растяжка для улучшения гибкости', 20)
        ]

        cursor.executemany(
            "INSERT INTO trainings (id, name, description, max_people) VALUES (?, ?, ?, ?)",
            trainings
        )

        # Расписание (на ближайшие 7 дней)
        schedule_data = []
        base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for day in range(7):
            current_date = base_date + timedelta(days=day)

            # Йога - утро
            schedule_data.append((
                1,
                (current_date + timedelta(hours=10)).strftime('%Y-%m-%d %H:%M:%S'),
                15
            ))

            # Силовая - вечер
            schedule_data.append((
                2,
                (current_date + timedelta(hours=18)).strftime('%Y-%m-%d %H:%M:%S'),
                10
            ))

            # Стретчинг - утро следующего дня
            if day < 6:
                schedule_data.append((
                    3,
                    (current_date + timedelta(days=1, hours=9)).strftime('%Y-%m-%d %H:%M:%S'),
                    20
                ))

        cursor.executemany(
            "INSERT INTO schedule (training_id, datetime, available_slots) VALUES (?, ?, ?)",
            schedule_data
        )

    def user_exists(self, user_id: int) -> bool:
        """Проверяет существование пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None

    def add_user(self, user_id: int, name: str, phone: str, username: str):
        """Добавляет нового пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, name, phone, username)
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, phone, username))
            conn.commit()

    def get_available_trainings(self) -> List[Dict]:
        """Возвращает список доступных тренировок"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.id, t.name, s.datetime as time 
                FROM trainings t
                JOIN schedule s ON t.id = s.training_id
                WHERE s.available_slots > 0
                AND s.datetime > datetime('now')
                ORDER BY s.datetime
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def get_available_dates(self, training_id: int) -> List[Dict]:
        """Возвращает доступные даты для тренировки"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, datetime as date_str
                FROM schedule 
                WHERE training_id = ? 
                AND available_slots > 0
                AND datetime > datetime('now')
            ''', (training_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_schedule(self, schedule_id: int) -> Optional[Dict]:
        """Возвращает информацию о расписании"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.*, t.name as training_name
                FROM schedule s
                JOIN trainings t ON s.training_id = t.id
                WHERE s.id = ?
            ''', (schedule_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

    def create_booking(self, user_id: int, schedule_id: int) -> bool:
        """Создает запись на тренировку"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT available_slots FROM schedule WHERE id = ?",
                (schedule_id,)
            )
            result = cursor.fetchone()

            if result and result[0] > 0:
                cursor.execute('''
                    INSERT INTO bookings (user_id, schedule_id)
                    VALUES (?, ?)
                ''', (user_id, schedule_id))

                cursor.execute('''
                    UPDATE schedule 
                    SET available_slots = available_slots - 1 
                    WHERE id = ?
                ''', (schedule_id,))

                conn.commit()
                return True
            return False

    def get_user_bookings(self, user_id: int) -> List[Dict]:
        """Возвращает записи пользователя"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    t.name as training_name,
                    s.datetime as date,
                    b.status
                FROM bookings b
                JOIN schedule s ON b.schedule_id = s.id
                JOIN trainings t ON s.training_id = t.id
                WHERE b.user_id = ?
                ORDER BY s.datetime DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]


# Для тестирования базы данных
if __name__ == "__main__":
    db = Database("test.db")
    print("База данных инициализирована успешно!")
    trainings = db.get_available_trainings()
    print("Доступные тренировки:", trainings)