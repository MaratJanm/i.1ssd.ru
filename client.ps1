
        $logFilePath = ".\client.log"
        $apiUrl = "http://i.1ssd.ru/temperatures"
        $company = "a767b5bf63517697a43a1562d87d2c0b0d724249db4d768b6eb1b27eb2593856" 

        # ������� ��� ��������� ����������� ������ � ���������� SMART
        function Get-DiskData {
            $diskData = @()
            $smartParameters = @('241', '243', '228', '005', '009', '170', '174', '184', '187', '194', '192', '199', '197', '230', '231')

            # ��������� ������ � ������ � ������� Get-PhysicalDisk � Get-StorageReliabilityCounter
            $disks = Get-PhysicalDisk | Sort-Object -Property Number
            $index = 0
            foreach ($disk in $disks) {
                $diskName = $disk.DeviceID
                $reliabilityData = Get-StorageReliabilityCounter -PhysicalDisk $disk

                $temperatureCelsius = $null
                $parameters = @{}

                if ($reliabilityData) {
                    $temperatureCelsius = $reliabilityData.Temperature

                    # ��������� ���������� SMART
                    $driveLetter = [char](97 + $index)  # 'a' ���������� � 97 � ASCII
                    $drivePath = "/dev/sd$driveLetter"
                    Write-Output $drivePath
                    $index++  # ����������� ������� ����� ������ ��������
                    
                    foreach ($param in $smartParameters) {
                        $output = & .\smartctl.exe -A $drivePath | Select-String "$param"
                        $pattern = '(\d+)$'

                        if ($output -match $pattern) {
                            $matchedValue = $matches[1]
                            $parameters[$param] = [int]$matchedValue  # �������������� � ����� �����
                        } else {
                            $parameters[$param] = $null  # ���� �������� �� ������, ���������� ��� null
                        }
                    }
                }

                $diskData += @{ "disk" = $disk.FriendlyName; "temperature" = $temperatureCelsius; "parameters" = $parameters }
            }

            return $diskData
        }

        # ������� ��� ���������� ������
        function Filter-DiskData {
            param ([array]$diskData)
            return $diskData | Where-Object {
                $_.disk -ne $null -and
                $_.temperature -ne $null -and 
                $_.parameters -ne $null
            }
        }

        # ������� ��� �������� ������ �� ������
        function Send-DataToServer {
            param ([string]$apiUrl, [string]$computerName, [array]$diskData, [string]$company)

            $payload = @{
                computer_name = $computerName
                company = $company  # ���������� �������� company
                temperatures = @()
            }

            foreach ($data in $diskData) {
                $tempData = @{
                    disk = $data.disk
                    temperature = $data.temperature
                    parameters = $data.parameters
                }
                $payload.temperatures += $tempData
            }

            $jsonPayload = $payload | ConvertTo-Json -Depth 5
            Write-Output "������������ JSON-�������: $jsonPayload"

            try {
                $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $jsonPayload -ContentType "application/json"
                Write-Output "Server response: $($response.message)" | Out-File $logFilePath -Append
            } catch {
                Write-Output "������ ��� ������ API. ������ ���: $($_.Exception.Response.StatusCode.Value__) ���������: $($_.Exception.Message)" | Out-File $logFilePath -Append
            }
        }

        # �������� ����
        $computerName = $env:COMPUTERNAME

        $diskData = Get-DiskData
        $filteredDiskData = Filter-DiskData -diskData $diskData
        Send-DataToServer -apiUrl $apiUrl -computerName $computerName -diskData $filteredDiskData -company $company
        Start-Sleep -Seconds 5  # �������� ������ ������ 5 ������
        