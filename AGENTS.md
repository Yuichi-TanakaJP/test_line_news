# Repository Instructions

## Purpose and production boundary

This repository generates Japanese LINE memos from current news, YouTube transcripts, and disclosure-event data. It is used by scheduled Windows tasks in production.

- Treat configuration paths, generated-output paths, and processed-state paths as operational contracts.
- Do not run `run_market_news.ps1`, `run_youtube_stocks.ps1`, `run_youtube_watch.ps1`, `run_disclosure_events.ps1`, or `python -m line_news.line` merely to validate a change. These commands may fetch live data, send LINE messages, or advance processed state.
- Sending a message, changing a scheduled task, changing a production profile, or initializing/marking processed state requires an explicit user request.
- Prefer unit tests, dry-run modes, temporary inputs, and mocked network calls for validation.

## Sources of truth

- `configs/*.json` defines each profile's topic, source priority, freshness, sections, labels, file names, and output limits. Read the requested JSON before generating or changing an artifact; do not transfer rules between profiles.
- `.claude/skills/` is the canonical Skill tree. `.agents/skills/` is generated for Codex according to `skill-sync.json`.
- Edit a Skill only in `.claude/skills/<name>/`, then run `python scripts/sync_agent_skills.py --write` and commit both trees together.
- `README.md` documents the current pipeline and scheduled-task setup. Confirm code and config before relying on schedule details, because local Task Scheduler state can differ from Git.

## Data and secret safety

- Never read, print, stage, or commit `.env` values. Keep credentials only in `.env` or the process environment; update `.env.example` with names and safe placeholders only.
- Do not overwrite source transcripts, archived outputs, logs, or processed-state files unless the user explicitly asks for that operational action.
- Runtime files such as `message*.txt`, `transcript*.txt`, `processed_*.json`, lock files, logs, and `outputs/` are not fixtures and must not be committed.
- Preserve unrelated dirty or untracked files. If a requested change overlaps live runtime data, stop and report the conflict.

## Memo-generation contracts

### News profiles

- Follow the selected `configs/<profile>.json`, including source order, freshness limits, sections, impact labels, footer, and `format.max_chars`.
- Prefer dated primary sources. Every included item must have a usable source URL and a verified event date.
- Separate facts from inference. Exclude unresolved conflicting figures or mark them `要確認`; do not silently choose one.

### YouTube profiles

- Use only the configured `transcript_file` as evidence. Do not supplement it with web searches, older messages, remembered prices, or unsupported stock names.
- Determine video type from the transcript when the profile defines `video_types`; do not infer it from upload time alone.
- Correct obvious subtitle errors only when context supports the correction. Uncertain names and security codes remain `要確認`.
- If the transcript is empty, truncated, or covers only a narrow topic, state that limitation and omit unsupported sections instead of filling them.

### Completion checks

Creating an output file is not completion. Before reporting a memo as complete:

1. Re-read the exact output file configured for that profile.
2. Verify every material claim against the allowed input/source set.
3. Verify required sections, labels, dates, source URLs, and footer.
4. Count characters, not bytes, and confirm the configured maximum is respected.
5. Report generation, verification, and sending as separate states. Never claim a message was sent unless the send command succeeded.

## Development workflow

- Start from an up-to-date `main` and work on a dedicated branch or worktree. Do not commit directly to `main`.
- Keep production behavior changes separate from documentation or Skill-maintenance changes.
- For ordinary Python changes, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- For Skill changes, also run:

```powershell
.\.venv\Scripts\python.exe scripts\sync_agent_skills.py
```

- For disclosure-message checks, use `python -m line_news.disclosure --dry-run`; do not substitute the sending runner.
- State clearly when live fetching, Task Scheduler state, external APIs, or LINE delivery were not tested.

## CI scope maintenance

ファイルの追加・移動・用途変更時は [CI対象と更新手順](docs/ci-scope-policy.md) を確認する。新pathは自動除外せず、必要な場合だけ用途・参照を確認して同じPRでYAMLを更新する。変更範囲をローカル検証してまとめてpushし、同じheadのCI/レビューを無条件に再実行しない。

## Review and verification defaults

- **省略可**: 意味・動作・運用判断・契約・実行手順を変えないdocs/comment等。最終diffと関連syntax/link/outputを確認する。
- **通常**: 動作を変えるcode/UI/API/config/schedule/external I/O。独立レビューを1回行う。
- **重点**: auth/permission/secrets/billing/DB migration/production operation/広い影響。独立レビューに専門・security・rollback観点を含める。
- model/profile/reasoning effortはagentがリスクと不確実性から選ぶ。レビューの起動失敗・quota・認証・model利用不能は完了ではなく、その失敗だけを理由にdepthを下げない。利用可能な別手段で必要な結果を満たす。変更内容の再評価でdepthを変える場合は理由を記録する。
- 意味のあるレビュー後修正だけ再レビューする。typo/comment/evidenceだけなら最終diff確認とする。PRにdepthと理由・実施結果を記録する。
- ローカルのリスク相応の検証を主とし、Actionsは任意・既定スキップ。未実行やbilling停止はNOT_RUNでありPASSではない。それだけでmergeを止めないが、ローカル失敗・未解決指摘・必須証拠不足はHOLD。実際の強制branch ruleと明示のrepo例外を確認し、無断でbypassしない。
- この方針は削除・本番deploy・公開・課金・mergeの承認を代替しない。既存の固有安全・データ・UAT条件は保持する。
