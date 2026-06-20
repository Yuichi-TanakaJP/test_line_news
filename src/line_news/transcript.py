"""Fetch a YouTube video transcript and print it as plain text.

Usage:
    python -m line_news.transcript <video_url_or_id> [--langs ja,en] [--out transcript.txt]

Joins the timestamped caption snippets into a single text block so a downstream
LLM step can read it. Prefers Japanese, falls back to any available transcript
(manual or auto-generated). On failure, prints the reason to stderr and exits 1.

Note: youtube-transcript-api may be blocked from datacenter IPs (e.g. CI runners).
Run from a local machine if you hit "no transcript / blocked" errors.
"""
import argparse
import re
import sys

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


def extract_video_id(url_or_id: str) -> str:
    """Accept a bare ID or any common YouTube URL form and return the 11-char ID."""
    s = url_or_id.strip()
    # Already a bare ID.
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", s):
        return s
    # /live/<id>, /watch?v=<id>, youtu.be/<id>, /embed/<id>, /shorts/<id>
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be/)([0-9A-Za-z_-]{11})",
        r"(?:/live/)([0-9A-Za-z_-]{11})",
        r"(?:/embed/)([0-9A-Za-z_-]{11})",
        r"(?:/shorts/)([0-9A-Za-z_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, s)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract a video id from: {url_or_id!r}")


def fetch_text(video_id: str, langs: list[str]) -> str:
    """Return the full transcript as one whitespace-joined string."""
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=langs)
    except NoTranscriptFound:
        # Fall back to whatever transcript exists (any language, generated or not).
        transcript_list = api.list(video_id)
        transcript = next(iter(transcript_list))
        fetched = transcript.fetch()
    parts = [snip.text.strip() for snip in fetched if snip.text.strip()]
    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a YouTube transcript as text.")
    parser.add_argument("video", help="YouTube video URL or 11-char ID")
    parser.add_argument(
        "--langs",
        default="ja,en",
        help="Comma-separated language preference order (default: ja,en)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write transcript to this file instead of stdout",
    )
    args = parser.parse_args()

    try:
        video_id = extract_video_id(args.video)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    langs = [s.strip() for s in args.langs.split(",") if s.strip()]

    try:
        text = fetch_text(video_id, langs)
    except (TranscriptsDisabled, NoTranscriptFound):
        print(
            f"ERROR: no transcript available for {video_id} "
            "(captions disabled or not yet generated for this video).",
            file=sys.stderr,
        )
        sys.exit(1)
    except VideoUnavailable:
        print(f"ERROR: video {video_id} is unavailable.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 - surface any blocking/network issue clearly
        print(f"ERROR: failed to fetch transcript for {video_id}: {e}", file=sys.stderr)
        sys.exit(1)

    if not text:
        print(f"ERROR: transcript for {video_id} was empty.", file=sys.stderr)
        sys.exit(1)

    sys.stdout.reconfigure(encoding="utf-8")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        # Success message goes to stdout (not stderr): PowerShell runners use
        # $ErrorActionPreference=Stop, which treats any native stderr output as
        # a terminating error even on exit code 0.
        print(f"OK wrote {len(text)} chars to {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
