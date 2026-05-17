# 毎晩のニュースメモ生成 → LINE送信ランナー（ローカルWindowsタスク用）
# 1) claude -p (headless) が configs/market.json に従い message.txt を生成
# 2) python send_line.py が message.txt を LINE 送信
# 実行ログは logs\ にタイムスタンプ付きで保存。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $LogDir "run_$Stamp.log"

function Log($msg) {
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
  $line | Tee-Object -FilePath $Log -Append
}

Log "=== START market_news ==="

try {
  # 1) Claude (headless) で /news skill を起動し message.txt 生成
  #    プロフィールは第1引数（既定: market）
  $profile = if ($args.Count -ge 1 -and $args[0]) { $args[0] } else { "market" }
  Log "claude -p '/news $profile' generating message.txt ..."
  $null | & claude -p "/news $profile" `
      --allowed-tools "Skill,WebSearch,WebFetch,Read,Write,Glob" `
      --permission-mode acceptEdits 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "claude exited with code $LASTEXITCODE" }

  if (-not (Test-Path (Join-Path $Root "message.txt"))) {
    throw "message.txt was not created"
  }
  $size = (Get-Item (Join-Path $Root "message.txt")).Length
  Log "message.txt created ($size bytes)"

  # 2) LINE 送信
  Log "sending via send_line.py ..."
  & python send_line.py message.txt 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "send_line.py failed with code $LASTEXITCODE" }

  Log "=== DONE (success) ==="
}
catch {
  Log "ERROR: $($_.Exception.Message)"
  Log "=== DONE (failed) ==="
  exit 1
}
