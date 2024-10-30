
        $logFilePath = ".\client.log"
        $apiUrl = "http://i.1ssd.ru/temperatures"
        $company = "ca26ae3f3309a825ec386068f7382d2dfa0df46207c02a05a633bf44bd86f770"  # Значение параметра company (хешированный email)

        # Функция для получения IP-адреса компьютера
        function Get-ComputerIPAddress {
            $ipAddress = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias Ethernet).IPAddress
            return $ipAddress
        }

        # Функция для получения температуры дисков и параметров SMART
        function Get-DiskData {
            $diskData = @()

            # Получение данных о дисках с помощью Get-PhysicalDisk и Get-StorageReliabilityCounter
            $disks = Get-PhysicalDisk | Sort-Object -Property Number
            $index = 0
            foreach ($disk in $disks) {
                $diskName = $disk.DeviceID
                $reliabilityData = Get-StorageReliabilityCounter -PhysicalDisk $disk	
                $temperatureCelsius = $null
                $parameters = @{}
                for ($i = 1; $i -le 255; $i++) {
                    $Parameters[$i] = $null
                }
                $deviceModel = $null
                $modelFamily = $null
                $userCapacity = $null
                $firmwareVersion = $null

                if ($reliabilityData) {
                    $temperatureCelsius = $reliabilityData.Temperature

                    # Получение параметров SMART
                    $driveLetter = [char](97 + $index) # 'a' начинается с 97 в ASCII
                    $drivePath = "/dev/sd$driveLetter"
                    Write-Output $drivePath
                    $index++ # Увеличиваем счетчик после каждой итерации
                    $output = & .\smartctl.exe -a $drivePath 
                    
                    # Извлечение дополнительных параметров с использованием регулярного выражения
                    $deviceModel = ($output | Select-String -Pattern 'Device Model').Line -replace '^.*?:\s*', ''
                    $modelFamily = ($output | Select-String -Pattern 'Model Family').Line -replace '^.*?:\s*', ''
                    $userCapacity = ($output | Select-String -Pattern 'User Capacity').Line -replace '^.*?:\s*', ''
                    $firmwareVersion = ($output | Select-String -Pattern 'Firmware Version').Line -replace '^.*?:\s*', ''

                    foreach ($line in $output) {
                        # Проверяем, соответствует ли строка формату ID# ATTRIBUTE_NAME
                        if ($line -match '^\s*(\d+)\s+\S+\s+0x\S+\s+(\d+)\s+') {
                            $id = [int]$matches[1]  # ID параметра
                            $value = [int]$matches[2]  # Значение VALUE

                            # Сохраняем значение VALUE по ключу ID
                            $parameters[$id] = $value
                        }
                    }	
                }

                $diskData += @{ 
                    "disk" = $disk.FriendlyName
                    "temperature" = $temperatureCelsius
                    "parameters" = $parameters
                    "deviceModel" = $deviceModel
                    "modelFamily" = $modelFamily
                    "userCapacity" = $userCapacity
                    "firmwareVersion" = $firmwareVersion
                }
            }

            return $diskData
        }

        # Функция для фильтрации данных
        function Filter-DiskData {
            param (
                [array]$diskData
            )

            return $diskData | Where-Object {
                $_.disk -ne $null -and
                $_.temperature -ne $null -and 
                $_.parameters -ne $null
            }
        }

        # Функция для отправки данных на сервер
        function Send-DataToServer {
            param (
                [string]$apiUrl,
                [string]$computerName,
                [array]$diskData,
                [string]$company
            )

            $payload = @{

                computer_name = $computerName
                company = $company  # Используем параметр company
                temperatures = @()
            }

            foreach ($data in $diskData) {
                # Преобразуем ключи хэш-таблицы параметров в строки
                $stringParameters = @{}
                foreach ($key in $data.parameters.Keys) {
                    $stringParameters["$key"] = $data.parameters[$key]  # Преобразуем ключ в строку
                }

                $tempData = @{ 
                    disk = $data.disk
                    temperature = $data.temperature
                    parameters = $stringParameters  # Используем параметры с ключами в виде строк
                    deviceModel = $data.deviceModel
                    modelFamily = $data.modelFamily
                    userCapacity = $data.userCapacity
                    firmwareVersion = $data.firmwareVersion
                }

                $payload.temperatures += $tempData
            }

            $jsonPayload = $payload | ConvertTo-Json -Depth 5
            Write-Output "Отправляемый JSON-пейлоад: $jsonPayload"

            try {
                $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $jsonPayload -ContentType "application/json"
                Write-Output "Server response: $($response.message)" | Out-File $logFilePath -Append
            } catch {
                Write-Output "Ошибка при вызове API. Статус код: $($_.Exception.Response.StatusCode.Value__) Сообщение: $($_.Exception.Message)" | Out-File $logFilePath -Append
            }
        }

        # Основной цикл
        $ipAddress = Get-ComputerIPAddress
        $computerName = "$env:COMPUTERNAME ($ipAddress)"  # Добавляем IP к названию компьютера
        $diskData = Get-DiskData
        $filteredDiskData = Filter-DiskData -diskData $diskData
        Send-DataToServer -apiUrl $apiUrl -computerName $computerName -diskData $filteredDiskData -company $company
        Start-Sleep -Seconds 60  # Отправка данных каждые 60 секунд
        