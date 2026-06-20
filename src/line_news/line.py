"""Send a text message to LINE via the Messaging API push endpoint.

Usage:
    python -m line_news.line message.txt
    echo "hello" | python -m line_news.line

Reads LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID from the environment,
falling back to the repository-root .env file.
On HTTP failure, prints the status code and response body, then exits 1.
"""
import json
import os
import sys
import urllib.error
import urllib.request

from line_news.paths import ENV_PATH

API_URL = "https://api.line.me/v2/bot/message/push"


def load_dotenv(path=ENV_PATH):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def send_text(text, token=None, user_id=None):
    """Send one LINE text message and return the HTTP status."""
    load_dotenv(ENV_PATH)
    token = token or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = user_id or os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        raise ValueError(
            "LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID not set (env or .env)."
        )

    text = text.strip()
    if not text:
        raise ValueError("empty message.")
    if len(text) > 5000:
        text = text[:4997] + "..."

    payload = json.dumps({
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    text = text.strip()
    try:
        status = send_text(text)
        print(f"OK {status}")
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"FAILED HTTP {e.code}\n{body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"FAILED network error: {e.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
