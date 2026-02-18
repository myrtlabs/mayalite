# Changelog

All notable changes to MayaLite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-02-17

### Added
- Web search via Brave Search API with Claude tool_use
- Voice message transcription via OpenAI Whisper
- Image understanding via Claude vision
- Natural language reminders with persistent storage
- Document reading (PDF, TXT, DOCX)
- Export functionality (`/export memory|history|all`)
- Multi-model support (`/model sonnet|opus`)
- Token usage tracking (`/usage`)
- Daily digest with weather and reminders
- `mayalite` CLI with start/stop/status/logs/setup/check commands
- Dependency checking for portable deployment

### Fixed
- Async event loop crash in tool handlers (sync search method)

## [0.3.0] - 2026-02-17

### Added
- Collaborative workspace modes: single, shared-dm, group
- Per-user conversation history for shared-dm
- Group chat support (Telegram groups)
- `/catchup` command to summarize others' conversations
- Per-workspace user authorization

## [0.2.0] - 2026-02-17

### Added
- Multiple workspaces with `/workspace` switching
- Heartbeat scheduler (APScheduler)
- Memory compaction with `/compact`
- `HEARTBEAT.md` support for proactive checks

## [0.1.0] - 2026-02-17

### Added
- Initial release
- Telegram bot with polling (no open ports)
- Claude API integration
- Single workspace with SOUL.md, MEMORY.md, TOOLS.md
- Append-only memory with conversation history
- Commands: /start, /help, /clear, /remember, /status
- CLI test mode (no Telegram needed)

## Security Model

- No shell execution by design
- Sandboxed file access (workspace directories only)
- Polling-based (no open ports)
- API keys in config.yaml only (gitignored)
