from flask import Flask, request, jsonify, render_template, url_for, flash, redirect, send_file, after_this_request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from forms import RegistrationForm, LoginForm
from models import User, db
import hashlib
import zipfile
import os
import time

app = Flask(__name__)

# Конфигурация для подключения к PostgreSQL
app.config['SECRET_KEY'] = '12345678'  # Не забудь установить секретный ключ для безопасности
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:12345678@localhost:5432/temperatures'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
# Конфигурация для bcrypt и login manager
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Путь к файлам
CLIENT_PS1_PATH = './client.ps1'
CLIENT_ZIP_PATH = './client.zip'
TEMPLATE_ZIP_PATH = './client-template.zip'

# Маршрут для генерации файла client.ps1 с заменой значения переменной $company
@app.route('/generate-client', methods=['POST'])
def generate_client():
    try:
        user_email = current_user.email
        # Создаем хеш email
        email_hash = hashlib.sha256(user_email.encode()).hexdigest()


        # PowerShell скрипт с подстановкой значения хэша email
        powershell_script = f'''
        $logFilePath = ".\\client.log"
        $apiUrl = "http://i.1ssd.ru/temperatures"
        $company = "{email_hash}" 

        # Функция для получения температуры дисков и параметров SMART
        function Get-DiskData {{
            $diskData = @()
            $smartParameters = @('241', '243', '228', '005', '009', '170', '174', '184', '187', '194', '192', '199', '197', '230', '231')

            # Получение данных о дисках с помощью Get-PhysicalDisk и Get-StorageReliabilityCounter
            $disks = Get-PhysicalDisk | Sort-Object -Property Number
            $index = 0
            foreach ($disk in $disks) {{
                $diskName = $disk.DeviceID
                $reliabilityData = Get-StorageReliabilityCounter -PhysicalDisk $disk

                $temperatureCelsius = $null
                $parameters = @{{}}

                if ($reliabilityData) {{
                    $temperatureCelsius = $reliabilityData.Temperature

                    # Получение параметров SMART
                    $driveLetter = [char](97 + $index)  # 'a' начинается с 97 в ASCII
                    $drivePath = "/dev/sd$driveLetter"
                    Write-Output $drivePath
                    $index++  # Увеличиваем счетчик после каждой итерации
                    
                    foreach ($param in $smartParameters) {{
                        $output = & .\\smartctl.exe -A $drivePath | Select-String "$param"
                        $pattern = '(\d+)$'

                        if ($output -match $pattern) {{
                            $matchedValue = $matches[1]
                            $parameters[$param] = [int]$matchedValue  # Преобразование в целое число
                        }} else {{
                            $parameters[$param] = $null  # Если параметр не найден, отправляем как null
                        }}
                    }}
                }}

                $diskData += @{{ "disk" = $disk.FriendlyName; "temperature" = $temperatureCelsius; "parameters" = $parameters }}
            }}

            return $diskData
        }}

        # Функция для фильтрации данных
        function Filter-DiskData {{
            param ([array]$diskData)
            return $diskData | Where-Object {{
                $_.disk -ne $null -and
                $_.temperature -ne $null -and 
                $_.parameters -ne $null
            }}
        }}

        # Функция для отправки данных на сервер
        function Send-DataToServer {{
            param ([string]$apiUrl, [string]$computerName, [array]$diskData, [string]$company)

            $payload = @{{
                computer_name = $computerName
                company = $company  # Используем параметр company
                temperatures = @()
            }}

            foreach ($data in $diskData) {{
                $tempData = @{{
                    disk = $data.disk
                    temperature = $data.temperature
                    parameters = $data.parameters
                }}
                $payload.temperatures += $tempData
            }}

            $jsonPayload = $payload | ConvertTo-Json -Depth 5
            Write-Output "Отправляемый JSON-пейлоад: $jsonPayload"

            try {{
                $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $jsonPayload -ContentType "application/json"
                Write-Output "Server response: $($response.message)" | Out-File $logFilePath -Append
            }} catch {{
                Write-Output "Ошибка при вызове API. Статус код: $($_.Exception.Response.StatusCode.Value__) Сообщение: $($_.Exception.Message)" | Out-File $logFilePath -Append
            }}
        }}

        # Основной цикл
        $computerName = $env:COMPUTERNAME

        $diskData = Get-DiskData
        $filteredDiskData = Filter-DiskData -diskData $diskData
        Send-DataToServer -apiUrl $apiUrl -computerName $computerName -diskData $filteredDiskData -company $company
        Start-Sleep -Seconds 5  # Отправка данных каждые 5 секунд
        '''

  # Записываем PowerShell-скрипт в файл client.ps1
        with open(CLIENT_PS1_PATH, 'w') as ps_file:
            ps_file.write(powershell_script)

        # Создаем новый архив client.zip на основе client-template.zip
        with zipfile.ZipFile(TEMPLATE_ZIP_PATH, 'r') as template_zip:
            with zipfile.ZipFile(CLIENT_ZIP_PATH, 'w') as client_zip:
                # Копируем все файлы из шаблона
                for item in template_zip.infolist():
                    client_zip.writestr(item, template_zip.read(item.filename))
                
                # Добавляем новый файл client.ps1
                client_zip.write(CLIENT_PS1_PATH, arcname='client.ps1')

        return jsonify({"message": "Файл client.ps1 успешно создан и добавлен в архив client.zip"}), 200

    except Exception as e:
        app.logger.error(f"Ошибка при создании архива: {e}")
        return jsonify({"message": "Ошибка при создании архива"}), 500

# Маршрут для скачивания client.zip
@app.route('/download-client', methods=['GET'])
def download_client_zip():
    try:
        # Проверяем, существует ли файл client.zip
        if not os.path.exists(CLIENT_ZIP_PATH):
            app.logger.error("Файл client.zip не найден.")
            return jsonify({"message": "Файл не найден"}), 404

        # Логируем успешное обнаружение файла
        app.logger.info("Файл client.zip найден, начинаем скачивание.")


        # Отправляем файл для скачивания
        return send_file(CLIENT_ZIP_PATH, as_attachment=True)

    except Exception as e:
        app.logger.error(f"Ошибка при скачивании файла: {e}")
        return jsonify({"message": f"Ошибка при скачивании файла: {str(e)}"}), 500

        
# Модель для хранения данных о температуре и параметрах диска
class Temperature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    computer_name = db.Column(db.String(50), nullable=False)
    disk = db.Column(db.String(50), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    company = db.Column(db.String(50), nullable=False)

    # Дополнительные параметры диска
    parameter_241 = db.Column(db.BigInteger, nullable=True)
    parameter_243 = db.Column(db.BigInteger, nullable=True)
    parameter_228 = db.Column(db.BigInteger, nullable=True)
    parameter_005 = db.Column(db.BigInteger, nullable=True)
    parameter_009 = db.Column(db.BigInteger, nullable=True)
    parameter_170 = db.Column(db.BigInteger, nullable=True)
    parameter_174 = db.Column(db.BigInteger, nullable=True)
    parameter_184 = db.Column(db.BigInteger, nullable=True)
    parameter_187 = db.Column(db.BigInteger, nullable=True)
    parameter_192 = db.Column(db.BigInteger, nullable=True)
    parameter_194 = db.Column(db.BigInteger, nullable=True)
    parameter_197 = db.Column(db.BigInteger, nullable=True)
    parameter_199 = db.Column(db.BigInteger, nullable=True)
    parameter_230 = db.Column(db.BigInteger, nullable=True)
    parameter_231 = db.Column(db.BigInteger, nullable=True)

@app.route('/api/disk/<computer_name>/<disk_name>/parameter/<parameter_name>', methods=['GET'])
@app.route('/api/disk/<computer_name>/<disk_name>/parameter/<parameter_name>', methods=['GET'])
def get_parameter_data(computer_name, disk_name, parameter_name):
    try:
        # Получаем параметры для сортировки и пагинации
        start = int(request.args.get('start', 0))
        length = int(request.args.get('length', 10))
        order_column = int(request.args.get('order[0][column]', 0))  # Столбец для сортировки
        order_dir = request.args.get('order[0][dir]', 'desc')  # Направление сортировки

        # Определяем поле для сортировки
        if order_column == 0:  # Сортировка по времени
            order_by = Temperature.timestamp
        elif order_column == 1:  # Сортировка по значению параметра
            order_by = getattr(Temperature, parameter_name)
        else:
            order_by = Temperature.timestamp  # По умолчанию сортировка по времени

        # Применяем направление сортировки
        if order_dir == 'asc':
            order_by = order_by.asc()
        else:
            order_by = order_by.desc()

        # Получаем данные с учетом пагинации и сортировки
        parameter_data = Temperature.query.filter_by(computer_name=computer_name, disk=disk_name)\
                                          .with_entities(Temperature.timestamp, getattr(Temperature, parameter_name))\
                                          .order_by(order_by)\
                                          .offset(start).limit(length).all()

        total_records = Temperature.query.filter_by(computer_name=computer_name, disk=disk_name).count()

        # Преобразуем данные для ответа
        result = [{"timestamp": record.timestamp.isoformat(), "value": getattr(record, parameter_name)} for record in parameter_data]

        return jsonify({
            "draw": request.args.get('draw', 1),
            "recordsTotal": total_records,
            "recordsFiltered": total_records,
            "data": result
        }), 200
    except Exception as e:
        app.logger.error(f"Error fetching parameter data: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

# Модель для хранения TBW и комментариев
class AdditionalInfo(db.Model):
    __tablename__ = 'additionalinfo'  # Указание на таблицу в БД
    id = db.Column(db.Integer, primary_key=True)
    computer_name = db.Column(db.String, nullable=False)
    disk = db.Column(db.String, nullable=False)
    realtbw = db.Column(db.BigInteger, nullable=True)
    comment = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<AdditionalInfo {self.computer_name} - {self.disk} - TBW: {self.realtbw}>"

# Маршрут для сохранения TBW
@app.route('/api/save-tbw/<computer_name>/<disk_name>', methods=['POST'])
def save_tbw(computer_name, disk_name):
    try:
        data = request.get_json()
        tbw = data.get('tbw')

        if tbw is None:
            return jsonify({"message": "TBW is required"}), 400

        # Находим запись AdditionalInfo и обновляем TBW
        additional_info = AdditionalInfo.query.filter_by(computer_name=computer_name, disk=disk_name).first()

        if additional_info:
            additional_info.realtbw = tbw
        else:
            # Если записи нет, создаем новую
            additional_info = AdditionalInfo(computer_name=computer_name, disk=disk_name, realtbw=tbw)
            db.session.add(additional_info)

        db.session.commit()
        return jsonify({"message": "TBW updated successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error updating TBW: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

# Маршрут для сохранения комментария
@app.route('/api/save-comment/<computer_name>/<disk_name>', methods=['POST'])
def save_comment(computer_name, disk_name):
    try:
        data = request.get_json()
        comment = data.get('comment')

        if comment is None:
            return jsonify({"message": "Comment is required"}), 400

        # Находим запись AdditionalInfo и обновляем комментарий
        additional_info = AdditionalInfo.query.filter_by(computer_name=computer_name, disk=disk_name).first()

        if additional_info:
            additional_info.comment = comment
        else:
            # Если записи нет, создаем новую
            additional_info = AdditionalInfo(computer_name=computer_name, disk=disk_name, comment=comment)
            db.session.add(additional_info)

        db.session.commit()
        return jsonify({"message": "Comment updated successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error updating comment: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

# Добавление температуры и параметров для диска
@app.route('/temperatures', methods=['POST'])
def add_temperature():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid data"}), 400

        computer_name = data.get('computer_name')
        temperatures = data.get('temperatures')

        if not computer_name or not temperatures:
            return jsonify({"message": "Invalid data"}), 400

        for item in temperatures:
            disk = item['disk']
            new_temp = item['temperature']
            parameters = {k: (int(v) if v not in ["-", None] else None) for k, v in item.get('parameters', {}).items()}

            # Проверка на повторяющиеся записи в базе данных
            last_temp_record = Temperature.query.filter_by(computer_name=computer_name, disk=disk)\
                                                .order_by(Temperature.timestamp.desc()).first()

            if last_temp_record:
                time_diff = datetime.utcnow() - last_temp_record.timestamp
                temp_diff = abs(new_temp - last_temp_record.temperature)

                # Игнорируем запись, если изменение температуры слишком резкое за короткий промежуток времени
                if time_diff < timedelta(minutes=1) and temp_diff > 20:
                    print(f"Игнорирование температуры для {disk} на {computer_name}: {new_temp}°C "
                          f"(разница {temp_diff}°C за {time_diff.seconds} секунд)")
                    continue

            # Сохранение новых данных
            new_temp_record = Temperature(
                computer_name=computer_name,
                disk=disk,
                temperature=new_temp,
                parameter_241=parameters.get('241'),
                parameter_243=parameters.get('243'),
                parameter_228=parameters.get('228'),
                parameter_005=parameters.get('005'),
                parameter_009=parameters.get('009'),
                parameter_170=parameters.get('170'),
                parameter_174=parameters.get('174'),
                parameter_184=parameters.get('184'),
                parameter_187=parameters.get('187'),
                parameter_194=parameters.get('194'),
                parameter_192=parameters.get('192'),
                parameter_199=parameters.get('199'),
                parameter_197=parameters.get('197'),
                parameter_230=parameters.get('230'),
                parameter_231=parameters.get('231')
            )
            db.session.add(new_temp_record)
            db.session.commit()

        return jsonify({"message": "Данные успешно добавлены"}), 200
    except Exception as e:
        print(f"Ошибка при добавлении данных: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

# Получение дополнительной информации по диску
@app.route('/api/additionalinfo/<computer_name>/<disk_name>', methods=['GET'])
def get_additional_info(computer_name, disk_name):
    try:
        additional_info = AdditionalInfo.query.filter_by(computer_name=computer_name, disk=disk_name).first()

        if additional_info:
            result = {"tbw": additional_info.realtbw, "comment": additional_info.comment}
        else:
            result = {"tbw": None, "comment": None}

        return jsonify(result)
    except Exception as e:
        print(f"Ошибка при получении дополнительных данных: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

# Получение списка температур
@app.route('/api/temperatures', methods=['GET'])
def get_temperatures():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        # Получаем email текущего пользователя
        user_email = current_user.email
        
        # Создаем хеш email
        email_hash = hashlib.sha256(user_email.encode()).hexdigest()

        temperatures = Temperature.query.filter_by(company=email_hash).order_by(Temperature.timestamp.desc()).offset(offset).limit(per_page).all()

        result = [
            {
                "computer_name": temp.computer_name,
                "disk": temp.disk,
                "temperature": temp.temperature,
                "timestamp": temp.timestamp,
                "parameter_241": temp.parameter_241
            }
            for temp in temperatures
        ]
        return jsonify(result)
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return jsonify({"message": "Internal Server Error"}), 500

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Вы успешно вышли из системы.", "info")
    return redirect(url_for('login'))


# Главная страница
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/disk/<computer_name>/<disk_name>', methods=['GET'])
def disk_page(computer_name, disk_name):
    return render_template('disk.html', computer_name=computer_name, disk_name=disk_name)

@app.route('/api/disk/latest/<computer_name>/<disk_name>', methods=['GET'])
def get_latest_disk_data(computer_name, disk_name):
    try:
        # Запрашиваем последние данные о температуре и параметрах для диска
        disk_data = Temperature.query.filter_by(computer_name=computer_name, disk=disk_name)\
                                     .order_by(Temperature.timestamp.desc())\
                                     .limit(1).all()

        if not disk_data:
            return jsonify([]), 200  # Возвращаем пустой массив, если данных нет

        result = [{
            "timestamp": record.timestamp,
            "parameter_241": record.parameter_241,
            "parameter_243": record.parameter_243,
            "parameter_228": record.parameter_228,
            "parameter_005": record.parameter_005,
            "parameter_009": record.parameter_009,
            "parameter_170": record.parameter_170,
            "parameter_174": record.parameter_174,
            "parameter_184": record.parameter_184,
            "parameter_187": record.parameter_187,
            "parameter_194": record.parameter_194,
            "parameter_192": record.parameter_192,
            "parameter_199": record.parameter_199,
            "parameter_197": record.parameter_197,
            "parameter_230": record.parameter_230,
            "parameter_231": record.parameter_231,
            "temperature": record.temperature
        } for record in disk_data]

        return jsonify(result), 200
    except Exception as e:  # Исправляем catch на except
        app.logger.error(f"Error fetching disk data: {e}")
        return jsonify({"message": "Internal Server Error"}), 500
@app.route('/disk/<computer_name>/<disk_name>/parameter/<parameter_name>', methods=['GET'])
def parameter_page(computer_name, disk_name, parameter_name):
    return render_template('parameter.html', computer_name=computer_name, disk_name=disk_name, parameter_name=parameter_name)

@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Ваш аккаунт создан!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
    
    
@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('index'))  # Перенаправление на защищённую страницу
        else:
            flash('Вход не удался. Проверьте email и пароль.', 'danger')
    return render_template('login.html', form=form)

    
    
if __name__ == "__main__":
    try:
        with app.app_context():
            db.create_all()  # Создание таблиц при необходимости
            print("Таблицы проверены и созданы.")
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")

    app.run(host='0.0.0.0', port=8000)

