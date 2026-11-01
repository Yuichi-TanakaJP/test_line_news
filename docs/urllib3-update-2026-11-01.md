# urllib3部分更新（2026-11-01）

certifi反映後のmainから分離し、requirementsのurllib3だけを2.7.0→2.8.0へ更新。他固定版不変。実装Sol low、gpt-6-astra/high独立TLS/domain/rollbackレビュー阻害なし。

Python3.12.15隔離venvで15unit tests PASS、Requests verify=True、認証不要PyPIへのTLS200。候補OSV該当なし。実venv/LINE本送信/runner/processed state/scheduler/実.env/実API宛先/HTTPS proxyは未操作・未検証。直接TLS成功はproxy経路の証明ではない。

urllib3 2.8.0のHTTPS proxy TLS設定変更は実利用条件を別途確認。マージ/反映は別途承認。復旧は旧固定版と実導入版を揃えて利用processを再起動、旧脆弱版の復元は安全復旧とは扱わない。公式: https://github.com/urllib3/urllib3/releases/tag/2.8.0 。実施日2026-11-01 JST。
