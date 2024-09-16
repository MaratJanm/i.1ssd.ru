$logFilePath = "c:\users\director\code\ssdv.05\DiskData888.log"
$apiUrl = "http://i.1ssd.ru/temperatures"

# Функция для получения температуры дисков и параметра 241
function Get-DiskData {
    $diskData = @()

    # Получение данных о дисках с помощью Get-PhysicalDisk и Get-StorageReliabilityCounter
    $disks = Get-PhysicalDisk
    foreach ($disk in $disks) {
        $diskName = $disk.DeviceID
        $reliabilityData = Get-StorageReliabilityCounter -PhysicalDisk $disk

        $temperatureCelsius = "-"
        $parameter241 = "-"

        if ($reliabilityData) {
            $temperatureCelsius = $reliabilityData.Temperature

            # Попытка получить параметр 241
            $parameter241 = $reliabilityData | Where-Object { $_.CounterSetName -eq "Total LBAs Written" } | Select-Object -ExpandProperty CounterValue -ErrorAction SilentlyContinue
            if (-not $parameter241) {
                $parameter241 = "-"
            }
        }

        $diskData += @{
            "disk" = $disk.FriendlyName
            "temperature" = $temperatureCelsius
            "parameter241" = $parameter241
        }
    }

    return $diskData
}

# Функция для отправки данных на сервер
function Send-DataToServer {
    param (
        [string]$apiUrl,
        [string]$computerName,
        [array]$diskData
    )

    $payload = @{
        computer_name = $computerName
        temperatures = @()
    }

    foreach ($data in $diskData) {
        $payload.temperatures += @{
            disk = $data.disk
            temperature = $data.temperature
            parameter241 = $data.parameter241
        }
    }

    $jsonPayload = $payload | ConvertTo-Json
    $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $jsonPayload -ContentType "application/json"
    Write-Output "Server response: $($response.message)"
}

# Основной цикл
$computerName = $env:COMPUTERNAME
while ($true) {
    $diskData = Get-DiskData
    Send-DataToServer -apiUrl $apiUrl -computerName $computerName -diskData $diskData
    Start-Sleep -Seconds 5  # Отправка данных каждые 5 секунд
}
