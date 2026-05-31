# 株YouTube動画 → 銘柄+見立て抽出 → LINE送信ランナー（ローカルWindowsタスク用）
# 1) fetch_transcript.py が動画URLの字幕を transcript.txt に保存
# 2) claude -p (headless) が /youtube-stocks skill で message.txt を生成
# 3) python send_line.py が message.txt を LINE 送信
# 実行ログは logs\ にタイムスタンプ付きで保存。
#
# 使い方:
#   .\run_youtube_stocks.ps1 "https://www.youtube.com/live/XXXXXXXXXXX"
# 第1引数に動画URL(またはID)を渡す。当面は手動運用、将来チャンネル自動監視を追加予定。

param(
  [Parameter(Mandatory = $true)]
  [string]$VideoUrl
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }  # フォールバック

$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $LogDir "run_youtube_$Stamp.log"

function Log($msg) {
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
  $line | Tee-Object -FilePath $Log -Append
}

Log "=== START youtube_stocks ($VideoUrl) ==="

try {
  # 1) 字幕取得 → transcript.txt
  Log "fetching transcript ..."
  & $Py fetch_transcript.py $VideoUrl --out transcript.txt 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "fetch_transcript.py failed with code $LASTEXITCODE" }

  # 2) Claude (headless) で /youtube-stocks skill を起動し message.txt 生成
  Log "claude -p '/youtube-stocks' generating message.txt ..."
  $null | & claude -p "/youtube-stocks" `
      --model sonnet `
      --allowed-tools "Skill,Read,Write,Glob" `
      --permission-mode acceptEdits 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "claude exited with code $LASTEXITCODE" }

  if (-not (Test-Path (Join-Path $Root "message.txt"))) {
    throw "message.txt was not created"
  }
  $size = (Get-Item (Join-Path $Root "message.txt")).Length
  Log "message.txt created ($size bytes)"

  # 3) LINE 送信
  Log "sending via send_line.py ..."
  & $Py send_line.py message.txt 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "send_line.py failed with code $LASTEXITCODE" }

  Log "=== DONE (success) ==="
}
catch {
  Log "ERROR: $($_.Exception.Message)"
  Log "=== DONE (failed) ==="
  exit 1
}
