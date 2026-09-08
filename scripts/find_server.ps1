Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'ComfyUI|main.py' } | Select-Object ProcessId, CommandLine | Format-List
