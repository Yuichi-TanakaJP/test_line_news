import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise AssertionError("Unsafe test fixture substitution")
    return source.replace(old, new)


@unittest.skipUnless(os.name == "nt", "Windows PowerShell operational contract")
class NotificationDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.runtime = Path(self.temp.name) / "runtime"
        self.root.mkdir()
        self.runtime.mkdir()
        (self.runtime / "baseline.json").write_text("{}", encoding="utf-8")
        self.marker = self.root / "runner-calls.txt"
        source = (Path(__file__).parents[1] / "scripts/line-notifications/Run-LineNotification.ps1").read_text(encoding="utf-8-sig")
        source = replace_once(source, "$Root = 'C:\\Users\\yutaz\\dev\\test_line_news'", "$Root = '" + str(self.root) + "'")
        source = replace_once(source, "$Runtime = 'C:\\Users\\yutaz\\dev\\_config\\line-notifications'", "$Runtime = '" + str(self.runtime) + "'")
        source = replace_once(source, "$Py = Join-Path $Root '.venv\\Scripts\\python.exe'", "$Py = '" + sys.executable + "'")
        source = replace_once(source, "Local\\Yutaz-LineNotifications-v1", "Local\\Notification-Test-" + uuid.uuid4().hex)
        self.wrapper = Path(self.temp.name) / "wrapper.ps1"
        self.assertIn("$Root = '" + str(self.root) + "'", source)
        self.assertIn("$Runtime = '" + str(self.runtime) + "'", source)
        self.fixture_source = source
        self.wrapper.write_text(source, encoding="utf-8-sig")
        self.guard("print('Baseline guard passed')")
        self.runner(0)

    def guard(self, source):
        (self.runtime / "Guard-LineBaseline.py").write_text(source, encoding="utf-8")

    def runner(self, code):
        for name in ("youtube_watch", "market_news", "disclosure_events"):
            (self.root / ("run_" + name + ".ps1")).write_text(
                "param([string]$Config)\nAdd-Content -LiteralPath '" + str(self.marker) + "' -Value invoked\nexit " + str(code) + "\n",
                encoding="utf-8-sig",
            )

    def run_wrapper(self, profile="youtube_stocks_kamioka", check_only=False):
        self.assertEqual(self.wrapper.read_text(encoding="utf-8-sig"), self.fixture_source)
        args = [str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-File", str(self.wrapper), "-Profile", profile]
        if check_only:
            args.append("-CheckOnly")
        return subprocess.run(args, capture_output=True, timeout=25)

    def events(self):
        result = []
        for p in (self.runtime / "diagnostics").glob("*.jsonl"):
            result.extend(json.loads(line.lstrip("\ufeff")) for line in p.read_text(encoding="utf-8-sig").splitlines())
        return result

    def test_guard_404_is_classified_without_raw_output_or_delivery(self):
        self.guard("import sys\nprint('HTTP Error 404: private-url?token=TEST_SECRET', file=sys.stderr)\nraise SystemExit('Cannot establish video publication times; refusing to send.')")
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.marker.exists())
        event = self.events()[-1]
        self.assertEqual((event["stage"], event["reason"], event["exit_code"], event["http_statuses"]), ("baseline_guard", "feed_http_error", 1, [404]))
        stored = json.dumps(self.events())
        self.assertNotIn("TEST_SECRET", stored)
        self.assertNotIn("private-url", stored)
        self.assertNotIn(b"TEST_SECRET", result.stderr + result.stdout)

    def test_native_stderr_with_zero_exit_keeps_original_success_behavior(self):
        self.guard("import sys\nprint('stderr', file=sys.stderr)")
        self.assertEqual(self.run_wrapper().returncode, 0)
        self.assertEqual(self.marker.read_text().splitlines(), ["invoked"])
        self.assertEqual(self.events()[-1]["outcome"], "completed")

    def test_guard_failure_without_http_does_not_invent_a_status(self):
        self.guard("raise SystemExit(7)")
        self.assertEqual(self.run_wrapper().returncode, 1)
        event = self.events()[-1]
        self.assertEqual(event["reason"], "guard_process_failed")
        self.assertEqual(event["http_statuses"], [])
        self.assertEqual(event["exit_code"], 7)
        self.assertFalse(self.marker.exists())

    def test_success_calls_only_fake_runner_once_and_records_correlation(self):
        self.assertEqual(self.run_wrapper().returncode, 0)
        self.assertEqual(self.marker.read_text().splitlines(), ["invoked"])
        events = self.events()
        self.assertEqual(len({e["invocation_id"] for e in events}), 1)
        self.assertEqual((events[-1]["stage"], events[-1]["outcome"], events[-1]["exit_code"]), ("runner", "completed", 0))

    def test_runner_failure_retains_nonzero_exit_and_does_not_retry(self):
        self.runner(7)
        self.assertEqual(self.run_wrapper().returncode, 1)
        self.assertEqual(self.marker.read_text().splitlines(), ["invoked"])
        self.assertEqual((self.events()[-1]["reason"], self.events()[-1]["exit_code"]), ("runner_exit_nonzero", 7))

    def test_missing_baseline_is_logged_before_guard_or_runner(self):
        (self.runtime / "baseline.json").unlink()
        self.assertEqual(self.run_wrapper().returncode, 1)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.events()[-1]["stage"], "baseline_presence")

    def test_check_only_does_not_run_guard_runner_or_write_logs(self):
        self.guard("raise SystemExit(7)")
        self.assertEqual(self.run_wrapper(check_only=True).returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.events(), [])

    def test_market_daily_gate_remains_once_per_day(self):
        self.guard("raise SystemExit(7)")
        self.assertEqual(self.run_wrapper("market").returncode, 0)
        self.assertEqual(self.run_wrapper("market").returncode, 0)
        self.assertEqual(self.marker.read_text().splitlines(), ["invoked"])
        self.assertEqual(self.events()[-1]["reason"], "already_attempted_today")

    def test_log_write_failure_does_not_change_delivery_behavior(self):
        (self.runtime / "diagnostics").write_text("not a directory", encoding="utf-8")
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.marker.read_text().splitlines(), ["invoked"])
        self.assertIn(b"diagnostic log could not be written", result.stderr)

    def test_disclosure_keeps_guard_and_uses_its_fake_runner(self):
        self.assertEqual(self.run_wrapper("disclosure").returncode, 0)
        self.assertEqual(self.marker.read_text().splitlines(), ["invoked"])
        self.assertTrue(any(e["stage"] == "baseline_guard" and e["outcome"] == "completed" for e in self.events()))

    def test_fixture_substitution_fails_closed_on_whitespace_change(self):
        with self.assertRaises(AssertionError):
            replace_once("$Root  = 'live'", "$Root = 'live'", "$Root = 'isolated'")

    def test_stderr_interruption_preserves_old_state_write_behavior(self):
        state_marker = self.root / "simulated-state-write.txt"
        self.guard("import sys,time\nfrom pathlib import Path\nsys.stderr.write('synthetic guard warning\\n');sys.stderr.flush()\ntime.sleep(0.3)\nPath(" + repr(str(state_marker)) + ").write_text('changed')")
        baseline = Path(self.temp.name) / "baseline-native-call.ps1"
        baseline.write_text("$ErrorActionPreference = 'Stop'\n$Py = '" + sys.executable + "'\n$Runtime = '" + str(self.runtime) + "'\n$Profile = 'youtube_stocks_kamioka'\ntry { & $Py (Join-Path $Runtime 'Guard-LineBaseline.py') $Profile } catch { exit 1 }", encoding="utf-8-sig")
        exe = str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
        old = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-File", str(baseline)], capture_output=True, timeout=25)
        time.sleep(0.6)
        old_wrote_state = state_marker.exists()
        if state_marker.exists():
            state_marker.unlink()
        new = self.run_wrapper()
        time.sleep(0.6)
        self.assertEqual(old.returncode, 0)
        self.assertEqual(new.returncode, old.returncode)
        self.assertEqual(state_marker.exists(), old_wrote_state)
        self.assertEqual(self.marker.exists(), old.returncode == 0)

    def test_guard_launch_error_with_no_exit_code_refuses_runner(self):
        fake_python = self.root / "not-python.exe"
        fake_python.write_bytes(b"not an executable")
        self.fixture_source = replace_once(self.fixture_source, "$Py = '" + sys.executable + "'", "$Py = '" + str(fake_python) + "'")
        self.wrapper.write_text(self.fixture_source, encoding="utf-8-sig")
        self.assertEqual(self.run_wrapper().returncode, 1)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.events()[-1]["stage"], "baseline_guard")
