"""test_line_news パイプライン共通パッケージ。

毎日のニュース/株YouTube/株主優待を要約・検知して LINE に配信する一連の
CLI を提供する。各モジュールは ``python -m line_news.<name>`` で実行でき、
PowerShell ランナー（リポジトリルートの run_*.ps1）から呼び出される。

- line       : LINE Messaging API への送信（共有）
- transcript : YouTube 字幕取得
- watch      : チャンネル RSS の新着検知
- disclosure : 株主優待イベント通知
- paths      : リポジトリルート基準のパス解決（configs/.env/状態ファイル）
"""
