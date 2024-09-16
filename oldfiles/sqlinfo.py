import sqlite3

# Открываем соединение с базой данных
conn = sqlite3.connect('temperatures.db')

# Создаем курсор для выполнения SQL-запросов
cursor = conn.cursor()

# Выполняем запрос для получения информации о столбцах таблицы temperature
cursor.execute("PRAGMA table_info(temperature)")

# Извлекаем все строки результата запроса
columns_info = cursor.fetchall()

# Закрываем соединение с базой данных
conn.close()

# Выводим информацию о столбцах
for column in columns_info:
    print(f"Column ID: {column[0]}, Name: {column[1]}, Type: {column[2]}, Not Null: {column[3]}, Default Value: {column[4]}, Primary Key: {column[5]}")
