# 株YouTube動画 → 銘柄+見立て抽出 → LINE送信ランナー（ローカルWindowsタスク用）
# 1) line_news.transcript が動画URLの字幕を transcript.txt に保存
# 2) claude -p (headless) が /youtube-stocks skill で message.txt を生成
# 3) line_news.line が message.txt を LINE 送信
# 実行ログは logs\ にタイムスタンプ付きで保存。
#
# 使い方:
#   .\run_youtube_stocks.ps1 "https://www.youtube.com/live/XXXXXXXXXXX"
#   .\run_youtube_stocks.ps1 "https://www.youtube.com/watch?v=XXXX" -Config configs\youtube_stocks_kamioka.json
# 第1引数に動画URL(またはID)を渡す。-Config でプロフィール切替（既定は Sho's）。

param(
  [Parameter(Mandatory = $true)]
  [string]$VideoUrl,
  [string]$Config = "configs\youtube_stocks.json"
)

# Continue を使う: ネイティブコマンド(python/claude)の stderr 出力が Stop 下で
# 終了エラーに昇格して throw されるのを防ぐ。各呼び出し後に $LASTEXITCODE を明示
# チェックして手動 throw するため異常検知は失われない。重要 cmdlet は個別に Stop。
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }  # フォールバック

# 設定から字幕/送信本文ファイル名を読む（プロフィールごとに分離）
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $Root $Config }
if (-not (Test-Path $ConfigPath)) { throw "config not found: $ConfigPath" }
$Cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
$TranscriptFile = if ($Cfg.transcript_file) { $Cfg.transcript_file } else { "transcript.txt" }
$OutputFile     = if ($Cfg.output_file)     { $Cfg.output_file }     else { "message.txt" }

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
  Get-ChildItem $LogDir -Filter "*.log" -File |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

  # 1) 字幕取得 → transcript_file
  Log "fetching transcript ..."
  Remove-Item (Join-Path $Root $TranscriptFile) -ErrorAction SilentlyContinue
  & $Py -m line_news.transcript $VideoUrl --out $TranscriptFile 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "line_news.transcript failed with code $LASTEXITCODE" }

  # 2) Claude (headless) で /youtube-stocks skill を起動し output_file 生成
  #    プロンプトは明示形にする。引数だけ("/youtube-stocks")だと稀に
  #    「パスが送られた」と誤解され何も実行されないことがあるため。
  Log "claude -p '/youtube-stocks' generating $OutputFile ..."
  Remove-Item (Join-Path $Root $OutputFile) -ErrorAction SilentlyContinue
  $null | & claude -p "/youtube-stocks スキルを実行して、設定ファイル $Config に従い $TranscriptFile から $OutputFile を生成してください" `
      --model sonnet `
      --allowed-tools "Skill,Read,Write,Glob" `
      --permission-mode acceptEdits 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "claude exited with code $LASTEXITCODE" }

  if (-not (Test-Path (Join-Path $Root $OutputFile))) {
    throw "$OutputFile was not created"
  }
  $size = (Get-Item (Join-Path $Root $OutputFile)).Length
  Log "$OutputFile created ($size bytes)"

  # 3) LINE 送信
  Log "sending via line_news.line ..."
  & $Py -m line_news.line $OutputFile 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "line_news.line failed with code $LASTEXITCODE" }

  Log "=== DONE (success) ==="
}
catch {
  Log "ERROR: $($_.Exception.Message)"
  Log "=== DONE (failed) ==="
  exit 1
}
