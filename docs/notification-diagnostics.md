# 通知タスク前段の診断ログ

## 目的と範囲

2026-11-08のYouTube監視は終了1だったが、内側runnerのログがなく、当時の前段エラーを復元できなかった。公式RSSは調査時に取得でき、原因は未確定のまま残す。

`scripts/line-notifications/Run-LineNotification.ps1` を外側wrapperの版管理された正本とする。従来の実機wrapperを移入し、診断だけを追加した。guard、各runner、プロフィール、baseline、処理済み状態、タスク定義は移動・変更しない。内側runnerのRSS取得失敗をsuccessとして扱う既存動作も今回の変更対象外。

## 記録

実機runtime配下の `diagnostics/notification-<profile>-<UTC日付>.jsonl` に追記する。時刻はUTCで、同一実行はinvocation_idで結ぶ。

- 段階: environment / working_directory / baseline_presence / python_presence / claude_presence / mutex_create / mutex_wait / baseline_guard / runner。
- 状態: started / completed / failed / skipped。固定の理由コード、既知のnative終了コード、抽出できたHTTPステータスだけを記録。
- guardの出力はメモリ内で分類する。stderr、例外全文、パス、URL、字幕、生成文、環境変数、送信先、秘密値は診断ファイルへ保存しない。
- publication_times_unavailableはguardが公開日時を確認できなかったことを示す。http_statusesが空でも原因なしとは判定しない。stage_exceptionはその段階での例外であり詳細原因未確定。
- ログ書込失敗は固定の警告のみをstderrへ出し、送信・失敗判定・処理済み状態・同日予約を変更しない。ログの欠落を成功証拠にしない。
- CheckOnlyではguard/runnerを実行せず診断ファイルも作らない。ログから11月8日の原因を後付け推定しない。

## 隔離確認

全体検証: `.venv/Scripts/python.exe -m unittest discover -s tests -v`。
13件の専用テスト（うち12件はWindows PowerShellを実際に起動）では、root/runtime/Python/mutexを隔離先へ差し替え、合成guard・合成runnerだけを実行する。guard起動失敗、404、非HTTP失敗、stderr+終了0の従来成功、stderr後の状態書込を旧native呼出しと比較、差し替え失敗の安全停止、runner失敗、baseline欠落、CheckOnly、ログ書込失敗、market同日予約、disclosure分岐を確認する。実送信や実データ更新はしない。

## 承認後の配備と切戻し

1. マージ・実機配備の直前承認を得る。実機wrapperのSHAが事前確認値と一致することを確認し、対象wrapperを使用するタスクが実行中なら配備を待つ。
2. 実機wrapperのバイト列を専用scratchに退避し、マージ済み版のwrapperのみを同じ実行パスへ配置する。baseline/guard/プロフィール/タスク/処理済み記録は変更しない。
3. 実機配置後のSHA一致とCheckOnlyを確認する。検証目的で送信runnerやguardを起動しない。
4. 次の自然な実行でJSONLとTask Scheduler結果を照合する。まだ実行されていなければ実運用の原因取得は未確認とする。
5. 切戻しは退避したwrapperだけを元のバイト列へ戻す。診断ファイルと処理済み状態は削除しない。切戻しも実機反映として承認を得る。

実装担当: Codex。外部送信と処理済み状態を持つ共通wrapperのため高リスクとし、別モデルによる送信境界・終了判定・秘密値・切戻しの独立レビューを必須とする。ローカル検証を主とし、既存のSkill同期CI triggerは変更しない。新規scripts/docs/testは既存のpaths限定workflowに一致せず、自動検証は追加しない。

Windows PowerShellの旧wrapperと同じ未リダイレクトnative呼出しを実測した結果、stderr出力だけでは子プロセスは中断されず、終了0なら継続する。診断用のリダイレクトが新しい停止条件を導入しないよう、guard出力の収集時だけContinueを使用し、起動失敗（終了コードなし）と非0終了で停止する。stderr後に待機して合成状態を書き込むguardで、旧呼出しと新wrapperの終了・状態書込が同じことを隔離検証する。
