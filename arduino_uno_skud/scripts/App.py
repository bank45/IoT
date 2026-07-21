import serial
import threading
import time
from datetime import datetime
import psycopg2
from psycopg2 import sql

# --- НАСТРОЙКИ ---
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600

# Укажите здесь ваши данные для подключения к PostgreSQL
DB_CONFIG = {
    "dbname": "iot_security",
    "user": "postgres",
    "password": "147147",  # Замените на свой пароль
    "host": "localhost",
    "port": "5432"
}

# --- ИНИЦИАЛИЗАЦИЯ ПОДКЛЮЧЕНИЙ ---
try:
    # Подключение к PostgreSQL
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True  # Чтобы изменения сохранялись сразу
    cursor = conn.cursor()

    # Создаем таблицу логов, если её ещё нет
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            raw_message TEXT NOT NULL
        );
    """)
    print("[DB]: Успешное подключение к PostgreSQL. Таблица проверена.")
except Exception as e:
    print(f"[DB Ошибка]: Не удалось подключить БД: {e}")
    exit()

try:
    # Подключение к Arduino
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Ожидание инициализации платы
    print("[Serial]: Успешное подключение к Arduino.")
except Exception as e:
    print(f"[Serial Ошибка]: Не удалось подключить {SERIAL_PORT}: {e}")
    conn.close()
    exit()


# --- ЛОГИКА СОХРАНЕНИЯ В БД ---
def log_event_to_db(raw_line):
    """Анализирует строку от Arduino и записывает её в PostgreSQL с тегом события"""
    now = datetime.now()
    event_type = "INFO"  # По умолчанию обычная информация

    # Классифицируем события на основе текста от Arduino
    if "[ДОСТУП РАЗРЕШЕН]" in raw_line:
        event_type = "ACCESS_GRANTED"
    elif "[ОШИБКА]" in raw_line:
        event_type = "ACCESS_DENIED"
    elif "[ТРЕВОГА!]" in raw_line:
        event_type = "ALARM_ACTIVATED"
    elif "[Система разблокирована]" in raw_line:
        event_type = "ALARM_DEACTIVATED"
    elif "СИСТЕМА ОХРАНЫ ЗАПУЩЕНА" in raw_line:
        event_type = "SYSTEM_START"

    try:
        # Безопасная enterprise-вставка через плейсхолдеры %s
        insert_query = """
            INSERT INTO security_logs (timestamp, event_type, raw_message)
            VALUES (%s, %s, %s);
        """
        cursor.execute(insert_query, (now, event_type, raw_line))
        print(f" -> [БД Запись]: Событие '{event_type}' успешно сохранено.")
    except Exception as e:
        print(f" -> [БД Ошибка]: Не удалось записать лог: {e}")


# --- ФОНОВЫЙ ПОТОК ДЛЯ ЧТЕНИЯ ---
def read_from_arduino():
    """Постоянно слушает Arduino и отправляет данные на парсинг в БД"""
    while True:
        if ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    print(f"\n[Arduino]: {line}")
                    # Запускаем логирование в базу данных
                    log_event_to_db(line)
            except Exception as e:
                print(f"\n[Ошибка чтения порта]: {e}")
                break


# Запуск потока чтения
rx_thread = threading.Thread(target=read_from_arduino, daemon=True)
rx_thread.start()

print("\n=== IoT-интерфейс (Си + Python + PostgreSQL) готов ===")
print("Введите пароль для отправки на плату (или 'exit' для выхода):")

# --- ОСНОВНОЙ ЦИКЛ ВВОДА КОМАНД ---
try:
    while True:
        user_input = input()

        if user_input.lower() == 'exit':
            break

        if user_input:
            ser.write((user_input + '\n').encode('utf-8'))
except KeyboardInterrupt:
    print("\nЗавершение работы...")
finally:
    ser.close()
    cursor.close()
    conn.close()
    print("Все соединения закрыты.")
