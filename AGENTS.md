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
