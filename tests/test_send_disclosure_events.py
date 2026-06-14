import tempfile
import unittest
from pathlib import Path

from send_disclosure_events import (
    MAX_EVENTS_PER_RUN,
    build_message,
    load_processed,
    normalize_security_code,
    save_processed,
    select_message_items,
    select_unseen_yutai,
)


class DisclosureEventsTest(unittest.TestCase):
    def setUp(self):
        self.yutai = {
            "event_id": "yutai-1",
            "event_type": "yutai_change",
            "audience": "all",
            "security_code": "12340",
            "company_name": "テスト株式会社",
            "title": "株主優待制度の変更",
        }
        self.dividend = {
            "event_id": "dividend-1",
            "event_type": "dividend_change",
            "audience": "personal",
        }
        self.payload = {
            "target_date": "2026-06-11",
            "items": [self.yutai, self.dividend],
        }

    def test_selects_only_unseen_all_company_yutai(self):
        self.assertEqual(
            select_unseen_yutai(self.payload, set()),
            [self.yutai],
        )
        self.assertEqual(
            select_unseen_yutai(self.payload, {"yutai-1"}),
            [],
        )

    def test_message_contains_event_and_radar_link(self):
        message = build_message(
            self.payload,
            [self.yutai],
            "https://mini.example/",
        )
        self.assertIn("優待変更 | 1234 テスト株式会社", message)
        self.assertIn(
            "https://mini.example/tools/disclosure-radar",
            message,
        )
        self.assertIn("event=yutai-1", message)
        self.assertIn("range=7", message)

    def test_normalizes_only_five_digit_tdnet_code(self):
        self.assertEqual(normalize_security_code("12340"), "1234")
        self.assertEqual(normalize_security_code("1230"), "1230")
        self.assertEqual(normalize_security_code("130a0"), "130A")

    def test_processed_state_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "processed.json"
            save_processed({"b", "a"}, path)
            self.assertEqual(load_processed(path), {"a", "b"})

    def test_message_stays_below_line_limit_for_one_run(self):
        long_item = {
            **self.yutai,
            "company_name": "会" * 1000,
            "title": "長" * 1000,
        }
        items = [
            {**long_item, "event_id": f"event-{index}"}
            for index in range(MAX_EVENTS_PER_RUN)
        ]
        message = build_message(self.payload, items, "https://mini.example/")
        self.assertLessEqual(len(message), 4900)

    def test_select_message_items_stops_before_message_limit(self):
        items = [
            {
                **self.yutai,
                "event_id": "event-" + ("x" * 1000) + str(index),
                "company_name": "会" * 1000,
                "title": "長" * 1000,
            }
            for index in range(MAX_EVENTS_PER_RUN)
        ]

        selected = select_message_items(
            self.payload,
            items,
            "https://mini.example/",
            limit=1200,
        )

        self.assertGreater(len(selected), 0)
        self.assertLess(len(selected), len(items))
        self.assertGreater(
            len(
                build_message(
                    self.payload,
                    [*selected, items[len(selected)]],
                    "https://mini.example/",
                )
            ),
            1200,
        )
        self.assertLessEqual(
            len(build_message(self.payload, selected, "https://mini.example/")),
            1200,
        )


if __name__ == "__main__":
    unittest.main()
