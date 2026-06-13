# 保存済みTDNETデータから抽出された株主優待イベントをLINE通知する。
# 送信成功したイベントだけ処理済みに記録し、失敗時は次回再試行する。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) {
  New-Item -ItemType Directory -Path $LogDir | Out-Null
}
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $LogDir "disclosure_events_$Stamp.log"
$Lock = Join-Path $Root ".disclosure_events.lock"
$LockCreated = $false

function Log($msg) {
  "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" |
    Tee-Object -FilePath $Log -Append
}

Log "=== START disclosure_events ==="

try {
  Get-ChildItem $LogDir -Filter "disclosure_events_*.log" -File |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

  if (Test-Path $Lock) {
    $lockAge = (Get-Date) - (Get-Item $Lock).LastWriteTime
    if ($lockAge.TotalHours -lt 2) {
      Log "WARN: another disclosure_events run appears active. skipping."
      exit 0
    }
    Log "WARN: removing stale lock file older than 2 hours."
    Remove-Item $Lock -Force
  }

  New-Item -Path $Lock -ItemType File -Value "pid=$PID started=$(Get-Date -Format o)" |
    Out-Null
  $LockCreated = $true

  & $Py send_disclosure_events.py 2>&1 |
    Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) {
    throw "send_disclosure_events.py failed with code $LASTEXITCODE"
  }
  Log "=== DONE (success) ==="
}
catch {
  Log "ERROR: $($_.Exception.Message)"
  Log "=== DONE (failed) ==="
  exit 1
}
finally {
  if ($LockCreated) {
    Remove-Item $Lock -ErrorAction SilentlyContinue
  }
}
