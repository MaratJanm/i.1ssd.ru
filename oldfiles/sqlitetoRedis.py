import sqlite3
import redis

# Шаг 1: Экспорт данных из SQLite
conn = sqlite3.connect('temperatures.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM temperature")
rows = cursor.fetchall()
conn.close()

# Шаг 2: Импорт данных в Redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    for row in rows:
        r.hset(f"temperature:{row[0]}", mapping={'date': row[1], 'value': row[2]})
    print("Data successfully transferred to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
