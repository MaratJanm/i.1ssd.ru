from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# Указание полного пути к базе данных
db_path = os.path.join(os.path.dirname(__file__), 'temperatures.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

db = SQLAlchemy(app)

class Temperature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    computer_name = db.Column(db.String(50), nullable=False)
    disk = db.Column(db.String(50), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

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
            new_temp = Temperature(
                computer_name=computer_name,
                disk=item['disk'],
                temperature=item['temperature']
            )
            db.session.add(new_temp)
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
                "timestamp": temp.timestamp
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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
