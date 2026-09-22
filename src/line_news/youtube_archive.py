"""Append-only archive for generated YouTube summary memos.

The LINE runners generate short-lived message files that are overwritten on the
next video. This module preserves the generated summary before delivery without
copying the full transcript.

Archive layout:
outputs/youtube-summary-history/<profile>/<video_id>/<digest>.json

The digest makes repeated processing of the same exact summary idempotent while
preserving a second version if the generator produces different text later.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from line_news.paths import PROJECT_ROOT, resolve

DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "outputs" / "youtube-summary-history"
_VIDEO_ID_RE = re.compile(r"^[0-9A-Za-z_-]{11}$")


def extract_video_id(value: str) -> str:
    """Extract an 11-character YouTube video ID from an ID or common URL."""
    candidate = value.strip()
    if _VIDEO_ID_RE.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]

    if host == "youtu.be":
        path_id = parsed.path.strip("/").split("/", 1)[0]
        if _VIDEO_ID_RE.fullmatch(path_id):
            return path_id

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            if _VIDEO_ID_RE.fullmatch(video_id):
                return video_id
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"live", "shorts", "embed"}:
            if _VIDEO_ID_RE.fullmatch(parts[1]):
                return parts[1]

    raise ValueError(f"could not extract YouTube video id: {value!r}")


def _load_profile(config_path: Path) -> tuple[str, str | None]:
    with config_path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    profile = str(cfg.get("profile") or config_path.stem).strip()
    if not profile:
        raise ValueError("profile must not be empty")
    title = cfg.get("title")
    return profile, str(title) if title is not None else None


def archive_summary(
    *,
    config_path: Path,
    video_url: str,
    summary_path: Path,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    archived_at: dt.datetime | None = None,
) -> tuple[Path, bool]:
    """Persist one generated summary and return (path, created)."""
    video_id = extract_video_id(video_url)
    profile, profile_title = _load_profile(config_path)

    summary = summary_path.read_text(encoding="utf-8")
    if not summary.strip():
        raise ValueError(f"summary file is empty: {summary_path}")

    summary_bytes = summary.encode("utf-8")
    digest = hashlib.sha256(summary_bytes).hexdigest()
    output_dir = archive_root / profile / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{digest}.json"

    if output_path.exists():
        return output_path, False

    now = archived_at or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("archived_at must be timezone-aware")

    payload = {
        "schema_version": 1,
        "profile": profile,
        "profile_title": profile_title,
        "video_id": video_id,
        "video_url": video_url,
        "archived_at": now.isoformat(),
        "summary_sha256": digest,
        "summary_char_count": len(summary),
        "summary_byte_count": len(summary_bytes),
        "summary": summary,
    }

    tmp_path = output_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(output_path)
    return output_path, True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive a generated YouTube summary before LINE delivery."
    )
    parser.add_argument("--config", required=True, help="YouTube profile config JSON")
    parser.add_argument("--video-url", required=True, help="YouTube video URL or 11-char ID")
    parser.add_argument("--summary-file", required=True, help="Generated summary text file")
    parser.add_argument(
        "--archive-root",
        default=str(DEFAULT_ARCHIVE_ROOT),
        help="Archive root (default: outputs/youtube-summary-history)",
    )
    args = parser.parse_args()

    path, created = archive_summary(
        config_path=Path(resolve(args.config)),
        video_url=args.video_url,
        summary_path=Path(resolve(args.summary_file)),
        archive_root=Path(resolve(args.archive_root)),
    )
    state = "created" if created else "already archived"
    print(f"OK youtube summary {state}: {path}")


if __name__ == "__main__":
    main()
