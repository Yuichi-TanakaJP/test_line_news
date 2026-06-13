"""Notify unseen all-company shareholder benefit events via LINE."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from send_line import ENV_PATH, load_dotenv, send_text

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "processed_disclosure_events.json"
YUTAI_LABELS = {
    "yutai_new": "優待新設",
    "yutai_expand": "優待拡充",
    "yutai_change": "優待変更",
    "yutai_end": "優待廃止",
    "yutai_review": "優待要確認",
}
MAX_EVENTS_PER_RUN = 12


def normalize_security_code(code):
    normalized = str(code).strip().upper()
    if (
        len(normalized) == 5
        and normalized.isalnum()
        and normalized.isascii()
        and normalized.endswith("0")
    ):
        return normalized[:-1]
    return normalized


def fetch_latest(api_base):
    url = f"{api_base.rstrip('/')}/disclosure-events/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def select_unseen_yutai(payload, processed_ids):
    return [
        item
        for item in payload.get("items", [])
        if item.get("audience") == "all"
        and item.get("event_type") in YUTAI_LABELS
        and item.get("event_id") not in processed_ids
    ]


def build_message(payload, items, mini_tools_base):
    lines = [f"【株主優待の開示】{payload.get('target_date', '')}"]
    for item in items:
        label = YUTAI_LABELS[item["event_type"]]
        code = normalize_security_code(item.get("security_code", ""))[:10]
        company_name = str(item.get("company_name", ""))[:80]
        title = str(item.get("title", ""))[:240]
        lines.extend(
            [
                "",
                f"{label} | {code} {company_name}",
                title,
            ]
        )
    if mini_tools_base:
        radar_url = f"{mini_tools_base.rstrip('/')}/tools/disclosure-radar"[:400]
        lines.extend(["", f"一覧: {radar_url}"])
    return "\n".join(lines)


def load_processed(path=STATE_PATH):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()
    values = payload.get("processed_event_ids", [])
    return {value for value in values if isinstance(value, str)}


def save_processed(processed_ids, path=STATE_PATH):
    payload = {"processed_event_ids": sorted(processed_ids)[-1000:]}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--init",
        action="store_true",
        help="Mark current yutai events as processed without sending.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message without sending or updating state.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    load_dotenv(ENV_PATH)
    api_base = os.environ.get("MARKET_INFO_API_BASE_URL", "").strip()
    mini_tools_base = os.environ.get("MINI_TOOLS_BASE_URL", "").strip()
    if not api_base:
        print("ERROR: MARKET_INFO_API_BASE_URL not set (env or .env).", file=sys.stderr)
        return 2

    try:
        payload = fetch_latest(api_base)
        processed = load_processed()
        all_unseen = select_unseen_yutai(payload, processed)
        if not all_unseen:
            print("No new shareholder benefit events.")
            return 0

        if args.init:
            current_ids = {
                item["event_id"]
                for item in select_unseen_yutai(payload, set())
            }
            save_processed(processed | current_ids)
            print(f"Initialized {len(current_ids)} event(s).")
            return 0

        unseen = all_unseen[:MAX_EVENTS_PER_RUN]
        event_ids = {item["event_id"] for item in unseen}
        message = build_message(payload, unseen, mini_tools_base)
        if len(message) > 4900:
            raise ValueError("disclosure event message exceeds 4900 characters")
        if args.dry_run:
            print(message)
            return 0

        status = send_text(message)
        save_processed(processed | event_ids)
        print(f"OK {status}: sent {len(unseen)} event(s).")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(f"FAILED HTTP {exc.code}\n{body}", file=sys.stderr)
    except urllib.error.URLError as exc:
        print(f"FAILED network error: {exc.reason}", file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
