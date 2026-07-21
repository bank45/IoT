import serial
import threading
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse # <-- Добавить эту строчку


# --- НАСТРОЙКИ ---
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600
DB_CONFIG = {
    "dbname": "iot_security",
    "user": "postgres",
    "password": "147147",  # Замените на свой
    "host": "localhost",
    "port": "5432"
}

app = FastAPI(title="IoT Security Dashboard API")

# Разрешаем CORS, чтобы фронтенд мог делать запросы к бэкенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные переменные для хранения состояния замка
lock_state = {"status": "ЗАБЛОКИРОВАНО", "last_update": ""}

# --- ПОДКЛЮЧЕНИЕ К БД И АРДУИНО ---
conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True
cursor = conn.cursor()

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)

def log_event_to_db(raw_line):
    global lock_state
    now = datetime.now()
    event_type = "INFO"

    if "[ДОСТУП РАЗРЕШЕН]" in raw_line:
        event_type = "ACCESS_GRANTED"
        lock_state["status"] = "ОТКРЫТО"
    elif "[Дверь закрыта]" in raw_line or "Система снова заблокирована" in raw_line:
        event_type = "ACCESS_DENIED"
        lock_state["status"] = "ЗАБЛОКИРОВАНО"
    elif "[ТРЕВОГА!]" in raw_line:
        event_type = "ALARM_ACTIVATED"
        lock_state["status"] = "ТРЕВОГА"
    elif "[Система разблокирована]" in raw_line:
        event_type = "ALARM_DEACTIVATED"
        lock_state["status"] = "ЗАБЛОКИРОВАНО"

    lock_state["last_update"] = now.strftime("%H:%M:%S")

    cursor.execute(
        "INSERT INTO security_logs (timestamp, event_type, raw_message) VALUES (%s, %s, %s);",
        (now, event_type, raw_line)
    )

def read_uart():
    while True:
        if ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    log_event_to_db(line)
            except:
                break

threading.Thread(target=read_uart, daemon=True).start()

# --- API ENDPOINTS ---

class PasswordModel(BaseModel):
    password: str

@app.get("/", response_class=HTMLResponse)
def read_index():
    """Отдает HTML-страницу фронтенда прямо с сервера"""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/status")
def get_status():
    """Получить текущий статус замка"""
    return lock_state

@app.post("/api/open")
def send_password(data: PasswordModel):
    """Отправить пароль на Arduino из веб-интерфейса"""
    try:
        ser.write((data.password + '\n').encode('utf-8'))
        return {"status": "sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
def get_logs():
    """Получить последние 10 логов из PostgreSQL"""
    cursor.execute("SELECT id, to_char(timestamp, 'HH24:MI:SS'), event_type, raw_message FROM security_logs ORDER BY timestamp DESC LIMIT 10;")
    rows = cursor.fetchall()
    # Исправлено: берем элементы из кортежа по индексам
    return [{"id": r[0], "time": r[1], "type": r[2], "message": r[3]} for r in rows]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8085)
