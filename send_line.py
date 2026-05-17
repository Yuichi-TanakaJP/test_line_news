"""Send a text message to LINE via the Messaging API push endpoint.

Usage:
    python send_line.py message.txt
    echo "hello" | python send_line.py

Reads LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID from the environment,
falling back to a .env file in the same directory.
On HTTP failure, prints the status code and response body, then exits 1.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://api.line.me/v2/bot/message/push"
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def main():
    load_dotenv(ENV_PATH)
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("ERROR: LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID not set "
              "(env or .env).", file=sys.stderr)
        sys.exit(2)

    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        print("ERROR: empty message.", file=sys.stderr)
        sys.exit(2)

    # LINE text message hard limit is 5000 chars.
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
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"OK {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"FAILED HTTP {e.code}\n{body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"FAILED network error: {e.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
