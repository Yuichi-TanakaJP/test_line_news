param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('market','youtube_stocks','youtube_stocks_kamioka','youtube_stocks_bitasen','disclosure')]
  [string]$Profile,
  [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\yutaz\dev\test_line_news'
$Runtime = 'C:\Users\yutaz\dev\_config\line-notifications'

$Stage = 'environment'
$InvocationId = [Guid]::NewGuid().ToString('N')
$GuardFailureLogged = $false
$RunnerFailureLogged = $false
function Write-Diagnostic {
  param([string]$Outcome, [string]$Reason = 'none', $ExitCode = $null, [int[]]$HttpStatuses = @())
  if ($CheckOnly) { return }
  # Logging must not change delivery, processed-state or daily reservation behavior.
  try {
    $LogDirectory = Join-Path $Runtime 'diagnostics'
    $null = New-Item -ItemType Directory -Path $LogDirectory -Force -ErrorAction Stop
    $Path = Join-Path $LogDirectory ("notification-{0}-{1}.jsonl" -f $Profile, [DateTime]::UtcNow.ToString('yyyyMMdd'))
    $Event = [ordered]@{
      schema_version = 1
      at = [DateTimeOffset]::UtcNow.ToString('o')
      invocation_id = $InvocationId
      profile = $Profile
      stage = $Stage
      outcome = $Outcome
      reason = $Reason
      exit_code = $ExitCode
      http_statuses = @($HttpStatuses)
    }
    $Event | ConvertTo-Json -Compress -Depth 3 | Add-Content -LiteralPath $Path -Encoding UTF8 -ErrorAction Stop
  } catch {
    # Never log exception text, native output, command lines or credential values.
    [Console]::Error.WriteLine('Notification diagnostic log could not be written.')
  }
}
function Write-GuardFailure {
  param([string]$Text, $ExitCode)
  # Extract only allowlisted numbers and fixed classifications, never the source text.
  $HttpStatuses = @([regex]::Matches($Text, 'HTTP Error ([1-5][0-9]{2})(?:\D|$)') |
    ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Unique)
  $Reason = if ($HttpStatuses.Count -gt 0) {
    'feed_http_error'
  } elseif ($Text -match 'Cannot establish video publication times') {
    'publication_times_unavailable'
  } else { 'guard_process_failed' }
  Write-Diagnostic 'failed' $Reason $ExitCode $HttpStatuses
}
try {
  Write-Diagnostic 'started'
  $env:PATH = [Environment]::GetEnvironmentVariable('Path','User') + ';' + [Environment]::GetEnvironmentVariable('Path','Machine')
  $env:PYTHONIOENCODING = 'utf-8'
  $env:PYTHONUTF8 = '1'
  $Stage = 'working_directory'
  Set-Location -LiteralPath $Root
  $Stage = 'baseline_presence'
  if (-not (Test-Path -LiteralPath (Join-Path $Runtime 'baseline.json'))) { throw 'Notification baseline is missing; refusing to send.' }
  $Stage = 'python_presence'
  $Py = Join-Path $Root '.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $Py)) { throw 'Project Python not found.' }
  $Stage = 'claude_presence'
  if ($Profile -ne 'disclosure') { $null = Get-Command claude -ErrorAction Stop }
  if ($CheckOnly) { Write-Output "Preflight OK: $Profile"; exit 0 }
  # All profiles share this mutex because market and Sho's use message.txt.
  $Stage = 'mutex_create'
  $Mutex = New-Object System.Threading.Mutex($false, 'Local\Yutaz-LineNotifications-v1')
  $Acquired = $false
  try {
    $Stage = 'mutex_wait'
    Write-Diagnostic 'started'
    try { $Acquired = $Mutex.WaitOne([TimeSpan]::FromMinutes(55)) }
    catch [System.Threading.AbandonedMutexException] { $Acquired = $true }
    if (-not $Acquired) { throw 'Another notification is running; no message sent.' }
    if ($Profile -ne 'market') {
      $Stage = 'baseline_guard'
      Write-Diagnostic 'started'
      # The original unredirected native stderr does not terminate the child on Windows PS.
      # Capture with Continue so redirection does not introduce a new NativeCommandError gate.
      $PreviousPreference = $ErrorActionPreference
      $LASTEXITCODE = $null
      try {
        $ErrorActionPreference = 'Continue'
        $GuardOutput = @(& $Py (Join-Path $Runtime 'Guard-LineBaseline.py') $Profile 2>&1)
        $GuardCode = $LASTEXITCODE
      } finally { $ErrorActionPreference = $PreviousPreference }
      if ($null -eq $GuardCode -or $GuardCode -ne 0) {
        $GuardText = ($GuardOutput | ForEach-Object { [string]$_ }) -join "`n"
        Write-GuardFailure $GuardText $GuardCode
        $GuardFailureLogged = $true
        throw 'Past-data guard failed; no notification runner started.'
      }
      Write-Diagnostic 'completed' 'none' $GuardCode
      $GuardOutput = $null
      $GuardText = $null
    }
    $Stage = 'runner'
    Write-Diagnostic 'started'
    if ($Profile -eq 'market') {
      # At most one automated attempt per JST date, including uncertain failures.
      $JstNow = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTimeOffset]::UtcNow, 'Tokyo Standard Time')
      $Daily = Join-Path $Runtime ('market-attempt-' + $JstNow.ToString('yyyy-MM-dd') + '.json')
      if (Test-Path -LiteralPath $Daily) { Write-Diagnostic 'skipped' 'already_attempted_today'; Write-Output 'Market notification already attempted today; skipping.'; exit 0 }
      $Handle = [IO.File]::Open($Daily, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
      $Handle.Dispose()
      @{status='started';at=$JstNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $Daily -Encoding UTF8
      & "$PSHOME\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File (Join-Path $Root 'run_market_news.ps1')
      $Result = $LASTEXITCODE
      @{status= $(if ($Result -eq 0) {'completed'} else {'failed_do_not_retry_automatically'});exit_code=$Result;at=$JstNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $Daily -Encoding UTF8
    }
    elseif ($Profile -eq 'disclosure') {
      & "$PSHOME\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File (Join-Path $Root 'run_disclosure_events.ps1')
      $Result = $LASTEXITCODE
    }
    else {
      & "$PSHOME\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File (Join-Path $Root 'run_youtube_watch.ps1') -Config ('configs\' + $Profile + '.json')
      $Result = $LASTEXITCODE
    }
    if ($Result -ne 0) { Write-Diagnostic 'failed' 'runner_exit_nonzero' $Result; $RunnerFailureLogged = $true; throw "Notification runner failed (exit $Result). Check project logs." }
    Write-Diagnostic 'completed' 'none' $Result
  }
  finally {
    if ($Acquired) { $Mutex.ReleaseMutex() }
    $Mutex.Dispose()
  }

} catch {
  if (-not $GuardFailureLogged -and -not $RunnerFailureLogged) {
    Write-Diagnostic 'failed' 'stage_exception'
  }
  [Console]::Error.WriteLine(('Notification failed at stage: {0}. Check diagnostics.' -f $Stage))
  exit 1
}
