# 毎晩のニュースメモ生成 → LINE送信ランナー（ローカルWindowsタスク用）
# 1) claude -p (headless) が configs/market.json に従い message.txt を生成
# 2) python -m line_news.line が message.txt を LINE 送信
# 実行ログは logs\ にタイムスタンプ付きで保存。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# line_news パッケージ (editable install 済み) を含む venv の python を使う
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

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
  Get-ChildItem $LogDir -Filter "*.log" -File |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    # 失敗しても続ける。掃除は本処理の前段でしかなく、片付けが1件できな
    # かっただけで送信をやめる理由にならない。2026-08-30、7月分のログ1件が
    # アクセス拒否になり、$ErrorActionPreference='Stop' がここで try を
    # 抜けさせ、開始2秒で DONE (failed) になった。ニュース生成も送信も
    # 一度も走っていない。
    Remove-Item -Force -ErrorAction SilentlyContinue

  # 1) Claude (headless) で /news skill を起動し message.txt 生成
  #    プロフィールは第1引数（既定: market）
  $profile = if ($args.Count -ge 1 -and $args[0]) { $args[0] } else { "market" }
  Log "claude -p '/news $profile' generating message.txt ..."
  Remove-Item (Join-Path $Root "message.txt") -ErrorAction SilentlyContinue
  # --model を明示する。省略すると既定モデルが選ばれ、2026-08-16 以降は
  # 内容や時刻に関係なく即座に "API Error: Rate limit reached" で落ちていた
  # （12日連続）。手元で切り分け済み: --model を付ければ opus/sonnet/haiku
  # いずれも通り、付けないときだけ落ちる。同じ実行の3分後に走る
  # run_youtube_watch.ps1 は --model sonnet を渡していて成功しており、
  # アカウントの利用枠の問題ではないことがこれで分かる。
  $null | & claude -p "/news $profile" `
      --model sonnet `
      --allowed-tools "Skill,WebSearch,WebFetch,Read,Write,Glob" `
      --permission-mode acceptEdits 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "claude exited with code $LASTEXITCODE" }

  if (-not (Test-Path (Join-Path $Root "message.txt"))) {
    throw "message.txt was not created"
  }
  $size = (Get-Item (Join-Path $Root "message.txt")).Length
  Log "message.txt created ($size bytes)"

  # 生成物を日付つきで残す。message.txt は毎回消して作り直すので、これが
  # 無いと「最後の1回」しか手元に残らない。ログには全文が出ているが、
  # 30日で消える上に読み返す形になっていない。
  #
  # 残す理由は記録そのものより、スキルの指示が古びていないかを後から
  # 見比べられるようにするため。似たようなニュースばかりになっていても、
  # 1回ずつ見ている限り気づけない。
  $ArchiveDir = Join-Path $Root "outputs\news\$profile"
  New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null
  $ArchivePath = Join-Path $ArchiveDir ("{0}.md" -f (Get-Date -Format "yyyy-MM-dd"))
  # 同じ日に2回走ったら上書きする。日付単位で1本あればよく、連番にすると
  # 見比べるときにどれが本番か分からなくなる。
  Copy-Item (Join-Path $Root "message.txt") $ArchivePath -Force
  Log "archived to $ArchivePath"

  # 2) LINE 送信
  Log "sending via line_news.line ..."
  & $Py -m line_news.line message.txt 2>&1 | Tee-Object -FilePath $Log -Append
  if ($LASTEXITCODE -ne 0) { throw "line_news.line failed with code $LASTEXITCODE" }

  Log "=== DONE (success) ==="
}
catch {
  Log "ERROR: $($_.Exception.Message)"
  Log "=== DONE (failed) ==="
  exit 1
}
