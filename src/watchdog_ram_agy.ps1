# WATCHDOG RAM + WSL ERROR GUARD - POLYDIM / Antigravity
# Reglas: 20, 26, 27, 28e
# Umbrales: AGY > 600MB KILL | LangServer > 700MB KILL | Sistema > 85% ALERTA
# Extra: detecta crecimiento rapido (> 50MB en un ciclo) como señal temprana de loop

$LOG        = "E:\POLYDIM_EINSOF\.watchdog_ram.log"
$STATE_FILE = "E:\POLYDIM_EINSOF\.watchdog_state.json"
$TS         = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$LIMIT_AGY_MB       = 600
$LIMIT_LS_MB        = 700
$LIMIT_SYS_PCT      = 85
$GROWTH_ALERT_MB    = 80   # crecimiento en un ciclo = señal temprana de loop

# ---- RAM sistema ----
$os  = Get-CimInstance Win32_OperatingSystem
$tot = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$fre = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$use = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 1)
$pct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 1)

Add-Content $LOG ("[$TS] === CICLO === RAM: " + $use + "/" + $tot + " GB (" + $pct + "%)")

# ---- Cargar estado anterior (para detectar crecimiento) ----
$prev = @{}
if (Test-Path $STATE_FILE) {
    try { $prev = Get-Content $STATE_FILE | ConvertFrom-Json -AsHashtable } catch {}
}
$curr = @{}

# ---- Funcion: evaluar proceso ----
function Check-Proc {
    param($name, $limit)
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        $mb   = [math]::Round($p.WorkingSet64 / 1MB, 1)
        $key  = $name + "_" + $p.Id
        $prev_mb = if ($prev.ContainsKey($key)) { $prev[$key] } else { 0 }
        $delta = $mb - $prev_mb
        $curr[$key] = $mb

        if ($mb -gt $limit) {
            Add-Content $LOG ("[$TS] KILL $name PID " + $p.Id + " - " + $mb + "MB > LIMITE " + $limit + "MB")
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        } elseif ($delta -gt $script:GROWTH_ALERT_MB -and $prev_mb -gt 0) {
            Add-Content $LOG ("[$TS] WARN $name PID " + $p.Id + " - " + $mb + "MB (+" + $delta + "MB en ciclo) CRECIMIENTO RAPIDO")
        } else {
            Add-Content $LOG ("[$TS] OK   $name PID " + $p.Id + " - " + $mb + "MB (delta: +" + $delta + "MB)")
        }
    }
}

Check-Proc "Antigravity"    $LIMIT_AGY_MB
Check-Proc "language_server" $LIMIT_LS_MB

# ---- Guardar estado actual ----
$curr | ConvertTo-Json | Set-Content $STATE_FILE

# ---- Alerta RAM sistema ----
if ($pct -gt $LIMIT_SYS_PCT) {
    $alert = "RAM CRITICA: " + $pct + "% (" + $use + "/" + $tot + " GB) - POLYDIM Watchdog"
    Add-Content $LOG ("[$TS] !!! " + $alert)
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($alert, "POLYDIM Watchdog", 0, 48)
}

# ---- Purga de log AGY si supera 5MB (evita acumulacion de errores WSL) ----
$agy_log = "$env:APPDATA\Antigravity\logs\main.log"
if (Test-Path $agy_log) {
    $sz = (Get-Item $agy_log).Length
    if ($sz -gt 5MB) {
        Copy-Item $agy_log ($agy_log -replace "main.log","main.old.log") -Force
        Clear-Content $agy_log
        Add-Content $LOG ("[$TS] PURGA log AGY (" + [math]::Round($sz/1MB,1) + "MB) -> rotado")
    }
}

Add-Content $LOG ("[$TS] --- fin ciclo ---")
