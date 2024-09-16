from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
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
    parameter241 = db.Column(db.String(50), nullable=True)
    parameter243 = db.Column(db.String(50), nullable=True)
    parameter228 = db.Column(db.String(50), nullable=True)
    parameter005 = db.Column(db.String(50), nullable=True)
    parameter009 = db.Column(db.String(50), nullable=True)
    parameter170 = db.Column(db.String(50), nullable=True)
    parameter174 = db.Column(db.String(50), nullable=True)
    parameter184 = db.Column(db.String(50), nullable=True)
    parameter187 = db.Column(db.String(50), nullable=True)
    parameter194 = db.Column(db.String(50), nullable=True)
    parameter192 = db.Column(db.String(50), nullable=True)
    parameter199 = db.Column(db.String(50), nullable=True)
    parameter197 = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f"<Temperature {self.computer_name} - {self.disk} - {self.temperature}°C>"

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
            smart_attributes = item['smartAttributes']

            # Получение последней записи температуры для данного диска
            last_temp_record = Temperature.query.filter_by(computer_name=computer_name, disk=disk).order_by(Temperature.timestamp.desc()).first()

            # Добавление новой записи температуры
            new_temp_record = Temperature(
                computer_name=computer_name,
                disk=disk,
                temperature=new_temp,
                parameter241=smart_attributes.get('241', "-"),
                parameter243=smart_attributes.get('243', "-"),
                parameter228=smart_attributes.get('228', "-"),
                parameter005=smart_attributes.get('005', "-"),
                parameter009=smart_attributes.get('009', "-"),
                parameter170=smart_attributes.get('170', "-"),
                parameter174=smart_attributes.get('174', "-"),
                parameter184=smart_attributes.get('184', "-"),
                parameter187=smart_attributes.get('187', "-"),
                parameter194=smart_attributes.get('194', "-"),
                parameter192=smart_attributes.get('192', "-"),
                parameter199=smart_attributes.get('199', "-"),
                parameter197=smart_attributes.get('197', "-")
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
                "parameter241": temp.parameter241,
                "parameter243": temp.parameter243,
                "parameter228": temp.parameter228,
                "parameter005": temp.parameter005,
                "parameter009": temp.parameter009,
                "parameter170": temp.parameter170,
                "parameter174": temp.parameter174,
                "parameter184": temp.parameter184,
                "parameter187": temp.parameter187,
                "parameter194": temp.parameter194,
                "parameter192": temp.parameter192,
                "parameter199": temp.parameter199,
                "parameter197": temp.parameter197
            }
            for temp in query
        ]
        return jsonify(result)
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

@app.route('/api/disk/<computer_name>/<disk_name>', methods=['GET'])
def get_disk_data(computer_name, disk_name):
    try:
        temperatures = Temperature.query.filter_by(computer_name=computer_name, disk=disk_name).order_by(Temperature.timestamp.desc()).all()
        result = [
            {
                "timestamp": temp.timestamp,
                "temperature": temp.temperature,
                "parameter241": temp.parameter241,
                "parameter243": temp.parameter243,
                "parameter228": temp.parameter228,
                "parameter005": temp.parameter005,
                "parameter009": temp.parameter009,
                "parameter170": temp.parameter170,
                "parameter174": temp.parameter174,
                "parameter184": temp.parameter184,
                "parameter187": temp.parameter187,
                "parameter194": temp.parameter194,
                "parameter192": temp.parameter192,
                "parameter199": temp.parameter199,
                "parameter197": temp.parameter197
            }
            for temp in temperatures
        ]
        return jsonify(result)
    except Exception as e:
        print(f"Ошибка при получении данных для диска: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/disk/<computer_name>/<disk_name>')
def disk(computer_name, disk_name):
    return render_template('disk.html')

if __name__ == "__main__":
    try:
        with app.app_context():
            db.create_all()  # Убедимся, что таблицы созданы
            print("Таблицы проверены и созданы при необходимости.")
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
    app.run(host='0.0.0.0', port=8000)
