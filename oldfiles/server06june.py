from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Указание полного пути к базе данных
db_path = os.path.join(os.path.dirname(__file__), 'temperatures.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Temperature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    computer_name = db.Column(db.String(50), nullable=False)
    disk = db.Column(db.String(50), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    parameter241 = db.Column(db.String(50), nullable=True)  # Добавлено поле для параметра 241

    def __repr__(self):
        return f"<Temperature {self.computer_name} - {self.disk} - {self.temperature}°C - {self.parameter241}>"

@app.route('/temperatures', methods=['POST'])
def add_temperature():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"message": "Invalid data"}), 400
        computer_name = data.get('computer_name')
        temperatures = data.get('temperatures')
        if not computer_name or not temperatures:
            return jsonify({"message": "Invalid data"}), 400

        for item in temperatures:
            disk = item['disk']
            new_temp = item['temperature']
            parameter241 = str(item.get('parameter241', "-"))  # Преобразование в строку

            # Получение последней записи температуры для данного диска
            last_temp_record = Temperature.query.filter_by(computer_name=computer_name, disk=disk).order_by(Temperature.timestamp.desc()).first()

            if last_temp_record:
                time_diff = datetime.utcnow() - last_temp_record.timestamp
                temp_diff = abs(new_temp - last_temp_record.temperature)

                # Проверка разницы температуры и времени
                if time_diff < timedelta(minutes=1) and temp_diff > 20:
                    print(f"Игнорирование температуры для {disk} на {computer_name}: {new_temp}°C (разница {temp_diff}°C за {time_diff.seconds} секунд)")
                    continue

            # Добавление новой записи температуры
            new_temp_record = Temperature(
                computer_name=computer_name,
                disk=disk,
                temperature=new_temp,
                parameter241=parameter241
            )
            db.session.add(new_temp_record)

        db.session.commit()
        return jsonify({"message": "Данные успешно добавлены"}), 200
    except Exception as e:
        print(f"Ошибка при добавлении данных: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

@app.route('/api/temperatures', methods=['GET'])
def get_temperatures():
    try:
        subquery = db.session.query(
            Temperature.computer_name,
            Temperature.disk,
            db.func.row_number().over(
                partition_by=[Temperature.computer_name, Temperature.disk],
                order_by=Temperature.timestamp.desc()
            ).label('row_num'),
            Temperature
        ).subquery()

        query = db.session.query(subquery).filter(subquery.c.row_num <= 100).all()

        result = [
            {
                "computer_name": temp.computer_name,
                "disk": temp.disk,
                "temperature": temp.temperature,
                "timestamp": temp.timestamp,
                "parameter241": temp.parameter241
            }
            for temp in query
        ]
        print(result)  # Добавлен вывод данных для диагностики
        return jsonify(result)
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download_client():
    try:
        return send_from_directory(directory='/opt/myapp', path='client.ps1', as_attachment=True)
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    try:
        with app.app_context():
            db.create_all()  # Убедимся, что таблицы созданы
            print("Таблицы проверены и созданы при необходимости.")
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
    app.run(host='0.0.0.0', port=8000)
