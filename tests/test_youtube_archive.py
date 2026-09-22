import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from line_news.youtube_archive import archive_summary, extract_video_id


class YoutubeArchiveTest(unittest.TestCase):
    def test_extract_video_id_common_forms(self):
        video_id = "AbCdEf123_-"
        self.assertEqual(extract_video_id(video_id), video_id)
        self.assertEqual(
            extract_video_id(f"https://www.youtube.com/watch?v={video_id}&t=10"),
            video_id,
        )
        self.assertEqual(
            extract_video_id(f"https://youtu.be/{video_id}?si=abc"),
            video_id,
        )
        self.assertEqual(
            extract_video_id(f"https://www.youtube.com/live/{video_id}"),
            video_id,
        )

    def test_extract_video_id_rejects_invalid_value(self):
        with self.assertRaises(ValueError):
            extract_video_id("https://example.com/not-youtube")

    def test_archive_is_append_only_and_same_content_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "youtube_bitasen.json"
            summary = root / "message.txt"
            archive_root = root / "archive"

            config.write_text(
                json.dumps(
                    {
                        "profile": "youtube_stocks_bitasen",
                        "title": "ビタセン 優待メモ 📺",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary.write_text("▼ サマリー\nテスト要約です。\n", encoding="utf-8")
            timestamp = dt.datetime(2026, 9, 22, 9, 0, tzinfo=dt.timezone.utc)

            first_path, first_created = archive_summary(
                config_path=config,
                video_url="https://www.youtube.com/watch?v=AbCdEf123_-",
                summary_path=summary,
                archive_root=archive_root,
                archived_at=timestamp,
            )
            second_path, second_created = archive_summary(
                config_path=config,
                video_url="https://www.youtube.com/watch?v=AbCdEf123_-",
                summary_path=summary,
                archive_root=archive_root,
                archived_at=timestamp + dt.timedelta(hours=1),
            )

            self.assertTrue(first_created)
            self.assertFalse(second_created)
            self.assertEqual(first_path, second_path)

            payload = json.loads(first_path.read_text(encoding="utf-8"))
            # archive_summary reads the memo as text, so Windows CRLF is
            # normalized before the content digest and byte count are made.
            expected_summary = summary.read_text(encoding="utf-8")
            expected_bytes = expected_summary.encode("utf-8")
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["profile"], "youtube_stocks_bitasen")
            self.assertEqual(payload["video_id"], "AbCdEf123_-")
            self.assertEqual(payload["archived_at"], timestamp.isoformat())
            self.assertEqual(
                payload["summary_sha256"],
                hashlib.sha256(expected_bytes).hexdigest(),
            )
            self.assertEqual(payload["summary_byte_count"], len(expected_bytes))
            self.assertEqual(payload["summary_char_count"], len(expected_summary))
            self.assertEqual(payload["summary"], expected_summary)
            self.assertIn("テスト要約", payload["summary"])

            summary.write_text("別バージョンの要約\n", encoding="utf-8")
            third_path, third_created = archive_summary(
                config_path=config,
                video_url="AbCdEf123_-",
                summary_path=summary,
                archive_root=archive_root,
                archived_at=timestamp + dt.timedelta(hours=2),
            )

            self.assertTrue(third_created)
            self.assertNotEqual(first_path, third_path)
            self.assertTrue(first_path.exists())
            self.assertTrue(third_path.exists())

    def test_archive_rejects_empty_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "youtube.json"
            summary = root / "message.txt"
            config.write_text('{"profile":"youtube_test"}', encoding="utf-8")
            summary.write_text("   \n", encoding="utf-8")

            with self.assertRaises(ValueError):
                archive_summary(
                    config_path=config,
                    video_url="AbCdEf123_-",
                    summary_path=summary,
                    archive_root=root / "archive",
                )


if __name__ == "__main__":
    unittest.main()
