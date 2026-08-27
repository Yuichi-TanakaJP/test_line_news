# 株YouTubeチャンネル監視ランナー（毎日定期実行用）
# 1) line_news.watch が RSS で新着動画を検知（処理済みは除外）
# 2) 新着があれば 取得→抽出→LINE送信
# 3) 送信成功した動画だけ line_news.watch --mark で処理済みに記録
# 新着がなければ何もせず正常終了。実行ログは logs\ に保存。
#
# -Config で監視プロフィールを切り替えられる（既定は Sho's投資情報局）。
# チャンネル/状態ファイル/字幕ファイル/送信本文ファイルはすべて設定から読むため、
# 複数チャンネルをそれぞれ別タスクで独立監視できる。
#   .\run_youtube_watch.ps1                                       # Sho's
#   .\run_youtube_watch.ps1 -Config configs\youtube_stocks_kamioka.json  # 上岡
#
# 初回は一度 `python -m line_news.watch --init --config <設定>` で既存動画を
# 基準化してから このランナーをスケジュール登録すること（過去動画の一括処理を防ぐ）。

param(
  [string]$Config = "configs\youtube_stocks.json"
)

# Continue を使う: ネイティブコマンド(python/claude)が stderr に出力すると、
# Stop 下では PowerShell がそれを終了エラーに昇格させ throw してしまう
# (例: line_news.watch の「no new videos」は stderr なので毎回失敗扱いになる)。
# 本スクリプトは各ネイティブ呼び出し後に $LASTEXITCODE を明示チェックして手動で
# throw するため、Continue でも異常検知は失われない。重要な cmdlet には個別に
# -ErrorAction Stop を付ける。
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

# 設定から字幕/送信本文ファイル名を読む（プロフィールごとに分離して衝突を防ぐ）
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $Root $Config }
if (-not (Test-Path $ConfigPath)) { throw "config not found: $ConfigPath" }
$Cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
$TranscriptFile = if ($Cfg.transcript_file) { $Cfg.transcript_file } else { "transcript.txt" }
$OutputFile     = if ($Cfg.output_file)     { $Cfg.output_file }     else { "message.txt" }
# プロフィール識別子（設定ファイル名）をロック/一時ファイル名に使い、多重監視でも衝突しない
$ProfileName = [System.IO.Path]::GetFileNameWithoutExtension($ConfigPath)

$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $LogDir "watch_${ProfileName}_$Stamp.log"
$Lock = Join-Path $Root ".youtube_watch_$ProfileName.lock"
$LockCreated = $false
$IdsFile = $null

function Log($msg) {
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
  $line | Tee-Object -FilePath $Log -Append
}

Log "=== START youtube_watch ($ProfileName) ==="

try {
  # 古いログは溜まり続けると運用時の確認を邪魔するため、直近30日だけ残す。
  Get-ChildItem $LogDir -Filter "*.log" -File |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

  # 手動実行やタスク設定変更で多重起動しても二重送信しないようにする。
  if (Test-Path $Lock) {
    $lockAge = (Get-Date) - (Get-Item $Lock).LastWriteTime
    if ($lockAge.TotalHours -lt 2) {
      Log "WARN: another youtube_watch run appears active. skipping this run."
      Log "=== DONE (success) ==="
      exit 0
    }
    Log "WARN: removing stale lock file older than 2 hours."
    Remove-Item $Lock -Force
  }
  New-Item -Path $Lock -ItemType File -Value "pid=$PID started=$(Get-Date -Format o)" -ErrorAction Stop | Out-Null
  $LockCreated = $true

  # 1) 新着検知。stdout(動画ID)をファイルに出し、stderr はログへ。
  #    ($ErrorActionPreference=Stop 下で & ... 2>&1 を変数取り込みすると
  #     ストリーム挙動が不安定なため、stdoutはファイル経由で確実に読む)
  $IdsFile = Join-Path $Root ("new_ids_{0}_{1}_{2}.tmp" -f $ProfileName, $PID, $Stamp)
  & $Py -m line_news.watch --list --config $Config 1> $IdsFile 2>> $Log
  $listCode = $LASTEXITCODE

  if ($listCode -eq 2) {
    # フィード取得に失敗（全チャンネル取得不可）。取りこぼし防止のため
    # 「新着なし」とは区別し、何も処理せず次回に委ねる。
    Log "WARN: feed fetch failed (exit 2). skipping this run, will retry next time."
    Log "=== DONE (success) ==="
    exit 0
  }
  if ($listCode -ne 0) {
    throw "line_news.watch --list failed with code $listCode"
  }

  $ids = @(Get-Content $IdsFile -ErrorAction SilentlyContinue |
           Where-Object { $_ -match '^[0-9A-Za-z_-]{11}$' })
  Remove-Item $IdsFile -ErrorAction SilentlyContinue

  if ($ids.Count -eq 0) {
    Log "no new videos. nothing to do."
    Log "=== DONE (success) ==="
    exit 0
  }

  Log "new videos: $($ids -join ', ')"

  foreach ($id in $ids) {
    $url = "https://www.youtube.com/watch?v=$id"
    Log "--- processing $id ---"

    # 2a) 字幕取得 → transcript_file
    Remove-Item (Join-Path $Root $TranscriptFile) -ErrorAction SilentlyContinue
    & $Py -m line_news.transcript $url --out $TranscriptFile 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) {
      Log "WARN: transcript fetch failed for $id (exit $LASTEXITCODE). skip, not marking."
      continue
    }

    # 2b) Claude (headless) で抽出 → output_file
    Remove-Item (Join-Path $Root $OutputFile) -ErrorAction SilentlyContinue
    $null | & claude -p "/youtube-stocks スキルを実行して、設定ファイル $Config に従い $TranscriptFile から $OutputFile を生成してください" --model sonnet --allowed-tools "Skill,Read,Write,Glob" --permission-mode acceptEdits 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) {
      Log "WARN: claude extract failed for $id (exit $LASTEXITCODE). skip, not marking."
      continue
    }
    if (-not (Test-Path (Join-Path $Root $OutputFile))) {
      Log "WARN: $OutputFile missing for $id. skip, not marking."
      continue
    }

    # 2c) LINE 送信
    & $Py -m line_news.line $OutputFile 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) {
      Log "WARN: send failed for $id (exit $LASTEXITCODE). not marking (will retry next run)."
      continue
    }

    # 3) 成功時のみ処理済みに記録
    & $Py -m line_news.watch --mark $id --config $Config 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) {
      throw "line_news.watch --mark failed for $id with code $LASTEXITCODE"
    }
    Log "--- done $id ---"
  }

  Log "=== DONE (success) ==="
}
catch {
  Log "ERROR: $($_.Exception.Message)"
  Log "=== DONE (failed) ==="
  exit 1
}
finally {
  if ($IdsFile) {
    Remove-Item $IdsFile -ErrorAction SilentlyContinue
  }
  if ($LockCreated) {
    Remove-Item $Lock -ErrorAction SilentlyContinue
  }
}
