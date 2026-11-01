# certifi 更新検証（2026-11-01）

requirements.txtのcertifiだけを2026.5.20から2026.10.23へ更新。他の固定版は不変。

- 導入前の既存.venv: Python3.12.15、実導入certifi2026.07.22。定義と実導入に差がある。
- Requests bundleは同venvのcertifi/cacert.pem、Session.verify=True。確認プロセスのCA上書き環境変数4種は未設定。稼働タスクの環境は未確認。
- 使用経路はsrc/line_news/transcript.pyのYouTubeTranscriptApi→Requests。LINE送信・disclosure・watchはurllib.request.urlopenのため、この更新でそれらのCAを直接更新したとは扱わない。
- 公式PyPIの候補実在、非yanked、Python>=3.7、OSV queryで既知指摘なしを2026-11-01に再確認。安全全体の認定ではない。
- 指定scratchの新規venvへ既存手順に従いrequirementsとeditable projectを導入。unittest discover: 15件PASS。certifi2026.10.23、Requests bundle一致、verify=True、認証不要PyPI GETはTLS検証有効で200。
- gpt-6-astra/high独立レビュー: 阻害なし。LINE Git差分は実装側の一行差分確認を採用。実使用先TLSと稼働タスクの環境、配備/rollbackは未検証。
- LINE本送信、データ取得runner、processed state更新、Task Scheduler変更は未実施。マージ/配備は承認待ち。

反映前に既存実導入版を再取得して記録し、承認後にREADMEの既存pip手順で反映する。Git revertだけでは元の実導入2026.07.22へ戻らないため、復旧基準は配備直前実版とする。旧CA復元は脆弱性再導入になり得るため解消済みとしない。TLS検証無効化を復旧策にしない。

検証環境: C:/Users/yutaz/dev/_scratch/codex/2026-11-01/certifi-fix-01/line-venv。
出典: https://pypi.org/pypi/certifi/2026.10.23/json 、https://google.github.io/osv.dev/post-v1-query/