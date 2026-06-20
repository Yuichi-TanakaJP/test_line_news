"""リポジトリルート基準のパス解決。

パッケージは ``src/line_news/`` に置くが、設定ファイル・``.env``・実行時に
生成される状態/出力ファイル（``configs/``、``message.txt``、
``processed_videos.json`` など）はリポジトリルートに置く運用なので、
それらは常にこのルート基準で解決する。CWD には依存しない。
"""
import os
from pathlib import Path

# src/line_news/paths.py -> line_news -> src -> リポジトリルート
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = str(PROJECT_ROOT / ".env")

# 既定の設定/状態ファイル（呼び出し側が --config 等で上書き可能）
DEFAULT_YOUTUBE_CONFIG = str(PROJECT_ROOT / "configs" / "youtube_stocks.json")
DEFAULT_VIDEO_STATE = str(PROJECT_ROOT / "processed_videos.json")


def resolve(path: str) -> str:
    """相対パスをリポジトリルート基準の絶対パスにする（絶対パスはそのまま）。"""
    if os.path.isabs(path):
        return path
    return str(PROJECT_ROOT / path)
