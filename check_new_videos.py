"""Detect new videos on monitored YouTube channels via the public RSS feed.

Uses https://www.youtube.com/feeds/videos.xml?channel_id=... which needs no
API key and consumes no quota. New videos are those not yet recorded in the
state file (default: processed_videos.json).

Channels and limits are read from configs/youtube_stocks.json:
  channels[].channel_id      監視対象チャンネル
  watch.max_new_per_run      1回で出力する新着の上限 (既定 1)

Usage:
  python check_new_videos.py --list            未処理の新着動画IDを新しい順に出力 (markしない)
  python check_new_videos.py --mark <videoId>  指定IDを処理済みとして記録
  python check_new_videos.py --init            現在のフィード全件を処理済みにして基準化 (初回用)

--list の出力は1行1動画ID。呼び出し側スクリプトが各IDを処理し、成功後に
--mark で記録する想定。

--config で別プロフィール設定を指定できる(既定 configs/youtube_stocks.json)。
チャンネルや状態ファイル(state_file)は指定した設定から読むため、複数チャンネルを
別々の状態ファイルで独立監視できる。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "configs", "youtube_stocks.json")
DEFAULT_STATE = os.path.join(HERE, "processed_videos.json")
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def configured_state_path(cfg: dict) -> str:
    state = cfg.get("watch", {}).get("state_file") or DEFAULT_STATE
    if os.path.isabs(state):
        return state
    return os.path.join(HERE, state)


def load_state(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("processed", []))


def save_state(path: str, seen: set[str]) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"processed": sorted(seen)}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)


def _fetch_once(channel_id: str) -> list[dict]:
    url = FEED_URL.format(cid=channel_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml = resp.read().decode("utf-8", "replace")
    ids = re.findall(r"<yt:videoId>(.*?)</yt:videoId>", xml)
    pubs = re.findall(r"<published>(.*?)</published>", xml)
    titles = re.findall(r"<media:title>(.*?)</media:title>", xml)
    entries = [
        {"id": i, "published": p, "title": t}
        for i, p, t in zip(ids, pubs, titles)
    ]
    entries.sort(key=lambda e: e["published"], reverse=True)
    return entries


def fetch_feed_entries(channel_id: str, retries: int = 4) -> list[dict]:
    """Return feed entries [{id, published, title}], newest first.

    YouTube's RSS endpoint intermittently returns an empty/200 body or rate-
    limits when hit rapidly. Retry with backoff and treat an empty result as a
    transient failure so a hiccup never masquerades as "no new videos".
    Raises the last error if all attempts fail.
    """
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            entries = _fetch_once(channel_id)
            if entries:
                return entries
            last_err = RuntimeError("empty feed response")
        except Exception as e:  # noqa: BLE001 - retry any transient fetch error
            last_err = e
        if attempt < retries - 1:
            time.sleep(2 * (attempt + 1))  # 2s, 4s, 6s
    raise RuntimeError(f"feed fetch failed for {channel_id}: {last_err}")


def all_entries(cfg: dict) -> tuple[list[dict], int]:
    """Return (entries newest-first, number of channels that failed to fetch)."""
    entries: list[dict] = []
    errors = 0
    for ch in cfg.get("channels", []):
        cid = ch.get("channel_id", "")
        if not cid or cid.startswith("("):  # placeholder not yet filled in
            print(f"WARN: skipping channel without channel_id: {ch.get('name')}",
                  file=sys.stderr)
            continue
        try:
            entries.extend(fetch_feed_entries(cid))
        except Exception as e:  # noqa: BLE001 - surface fetch issues, keep going
            errors += 1
            print(f"WARN: failed to fetch feed for {cid}: {e}", file=sys.stderr)
    entries.sort(key=lambda e: e["published"], reverse=True)
    return entries, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect new YouTube videos via RSS.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="未処理の新着動画IDを出力")
    g.add_argument("--mark", metavar="VIDEO_ID", help="指定IDを処理済みに記録")
    g.add_argument("--init", action="store_true",
                   help="現在のフィード全件を処理済みにして基準化")
    parser.add_argument("--state", default=None, help="状態ファイルのパス")
    parser.add_argument("--config", default=CONFIG_PATH,
                        help="プロフィール設定ファイルのパス (既定 configs/youtube_stocks.json)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(HERE, config_path)
    cfg = load_config(config_path)
    state_path = args.state or configured_state_path(cfg)
    seen = load_state(state_path)

    if args.mark:
        seen.add(args.mark)
        save_state(state_path, seen)
        print(f"OK marked {args.mark} as processed ({len(seen)} total)")
        return

    if args.init:
        entries, errors = all_entries(cfg)
        for e in entries:
            seen.add(e["id"])
        save_state(state_path, seen)
        print(f"OK seeded {len(entries)} feed videos as processed "
              f"({len(seen)} total in state)", file=sys.stderr)
        if errors:
            sys.exit(2)
        return

    # --list
    max_new = int(cfg.get("watch", {}).get("max_new_per_run", 1))
    entries, errors = all_entries(cfg)
    # フィード取得に失敗した(全滅)場合は「新着なし」と区別して非ゼロ終了。
    # 取りこぼし防止のため、呼び出し側は次回再試行する想定。
    if errors and not entries:
        print("ERROR: could not fetch any channel feed; skipping this run.",
              file=sys.stderr)
        sys.exit(2)
    new = [e for e in entries if e["id"] not in seen]
    for e in new[:max_new]:
        print(e["id"])  # one video id per line (newest first)
    if not new:
        print("no new videos", file=sys.stderr)


if __name__ == "__main__":
    main()
