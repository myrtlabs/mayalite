# MayaLite v0.4

A minimal, secure AI assistant with workspace-scoped contexts. Telegram + Claude, no bloat.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Why MayaLite?

| Feature | MayaLite | Full Agent Frameworks |
|---------|----------|----------------------|
| Lines of code | ~2,000 | 15,000+ |
| Open ports | None (polling) | Webhooks required |
| Shell execution | ❌ Blocked by design | ✅ Full access |
| Setup time | 5 minutes | Hours |
| Dependencies | 10 packages | 50+ packages |

**MayaLite is for:** Personal AI assistants where you want simplicity, security, and full control.

## Features

### Core
- 🗂 **Workspaces** — Separate contexts for different domains (work, personal, projects)
- 🧠 **Memory** — Persistent MEMORY.md per workspace with auto-compaction
- 💬 **Telegram** — Polling-based (no open ports, no webhook exposure)
- 🔒 **Secure** — No shell exec, sandboxed file access, explicit allowlists

### v0.4 Additions
- 🔍 **Web Search** — Brave API with Claude tool_use
- 🎤 **Voice** — Whisper transcription for voice messages
- 🖼 **Vision** — Image understanding via Claude
- ⏰ **Reminders** — Natural language ("remind me in 2 hours...")
- 📄 **Documents** — PDF, TXT, DOCX reading and summarization
- 🤖 **Multi-Model** — Switch between Sonnet/Opus per workspace
- 📊 **Usage Tracking** — Token counts and cost estimates

## Quick Start

### 1. Check Dependencies

```bash
./mayalite check
```

### 2. Setup

```bash
./mayalite setup
```

### 3. Configure

```bash
./mayalite secrets
```

Interactive wizard walks you through:
- Telegram bot token (from @BotFather)
- Your Telegram user ID
- Anthropic API key or OAuth token
- Optional: Brave Search, OpenAI (Whisper)

Run `./mayalite secrets` anytime to update settings.

### 4. Run

```bash
./mayalite start    # Start in background
./mayalite status   # Check if running
./mayalite logs     # Tail logs
./mayalite stop     # Stop
```

## Telegram Setup

### Create a Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a display name (e.g., "Maya")
4. Choose a username (must end in `bot`, e.g., `MyMayaBot`)
5. Copy the token: `123456789:ABCdefGHIjklMNO...`

### Get Your User ID

1. Search for `@userinfobot` in Telegram
2. Send `/start`
3. It replies with your user ID (e.g., `8232145741`)

### Get a Group ID

1. Add your bot to the group
2. Run `./mayalite logs`
3. Send any message in the group
4. Look for: `📩 Message from user=... chat=-1234567890`
5. The negative number is your group ID

### Enable Group Messages (Important!)

By default, Telegram bots can only see commands in groups. To receive all messages:

1. Open `@BotFather`
2. Send `/mybots`
3. Select your bot
4. **Bot Settings** → **Group Privacy** → **Turn off**
5. **Remove and re-add** the bot to your group (required for the change to take effect)

### Auto-Start on Boot (macOS)

```bash
./mayalite enable   # Start on boot
./mayalite disable  # Don't start on boot
```

## Commands

### Chat Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/status` | Workspace info, model, usage |
| `/clear` | Clear conversation history |
| `/remember <text>` | Save to MEMORY.md |

### Workspaces

| Command | Description |
|---------|-------------|
| `/workspace` | List available workspaces |
| `/workspace <name>` | Switch to workspace |

### Search & Media

| Command | Description |
|---------|-------------|
| `/search <query>` | Web search |
| `/summarize` | Summarize last document |
| 🎤 *Send voice* | Auto-transcribed |
| 🖼 *Send photo* | Analyzed by Claude |
| 📄 *Send document* | PDF/TXT/DOCX parsed |

### Reminders

| Command | Description |
|---------|-------------|
| `/remind <time> <msg>` | Set reminder |
| `/reminders` | List pending |

Examples:
- `/remind in 2 hours Check the oven`
- `/remind tomorrow at 9am Call dentist`

### Model & Usage

| Command | Description |
|---------|-------------|
| `/model` | Show current model |
| `/model sonnet` | Switch to Sonnet |
| `/model opus` | Switch to Opus |
| `/usage` | Token stats and costs |
| `/usage reset` | Reset counters |

### Memory

| Command | Description |
|---------|-------------|
| `/compact` | Preview memory compaction |
| `/compact yes` | Apply compaction |
| `/catchup` | Summarize others' chats (shared-dm) |
| `/heartbeat` | Trigger heartbeat check |

### Export

| Command | Description |
|---------|-------------|
| `/export memory` | Export MEMORY.md |
| `/export history` | Export chat history |
| `/export all` | Export full workspace zip |

## Workspace Structure

```
workspaces/
├── _global/
│   ├── IDENTITY.md     # Who the bot is (shared across workspaces)
│   └── USER.md         # About the user
├── main/
│   ├── SOUL.md         # Workspace persona/instructions
│   ├── MEMORY.md       # Long-term memory (auto-updated)
│   ├── TOOLS.md        # Available tools/references
│   ├── HEARTBEAT.md    # Proactive check instructions
│   └── history.jsonl   # Conversation history
└── pricing/
    ├── SOUL.md         # "You are a pricing analyst..."
    └── ...
```

## Workspace Modes

| Mode | Use Case |
|------|----------|
| `single` | One user, one workspace (default) |
| `shared-dm` | Multiple users DM privately, shared memory |
| `group` | Telegram group chat, everyone sees everything |

Configure in `config.yaml`:

```yaml
workspaces:
  configs:
    pricing-team:
      mode: "shared-dm"
      authorized_users: [123456789, 987654321]
    
    family:
      mode: "group"
      telegram_group_id: -100123456789
```

## Configuration

See `config.yaml.example` for all options. Key sections:

```yaml
telegram:
  token: "BOT_TOKEN"
  authorized_users: [YOUR_TELEGRAM_ID]
  authorized_groups: [-1001234567890]  # Optional

claude:
  # API key (pay-as-you-go): sk-ant-api03-...
  # OAuth token (Max subscription): sk-ant-oat01-...
  api_key: "sk-ant-..."
  model: "claude-sonnet-4-20250514"
  max_tokens: 4096

# Optional features
brave:
  api_key: ""  # For web search

openai:
  api_key: ""  # For voice transcription

heartbeat:
  enabled: true
  interval_minutes: 30

digest:
  enabled: false
  time: "08:00"
  timezone: "America/New_York"
```

## Security Model

MayaLite is designed with security as a core constraint:

1. **No shell execution** — Cannot run system commands
2. **Sandboxed files** — Only workspace directories accessible
3. **Polling-based** — No open ports, no webhook exposure
4. **Explicit allowlist** — Only authorized Telegram users
5. **Secrets isolated** — API keys in config.yaml (gitignored)

## CLI Reference

```bash
./mayalite check    # Verify dependencies
./mayalite setup    # Create venv, install deps
./mayalite start    # Start bot in background
./mayalite stop     # Stop bot
./mayalite restart  # Stop + start
./mayalite status   # Check if running, show uptime
./mayalite logs     # Tail log file (Ctrl+C to exit)
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```

## Project Structure

```
v0.4/
├── mayalite           # CLI script
├── main.py            # Entry point
├── src/
│   ├── bot.py         # Telegram handlers
│   ├── claude.py      # Claude API client
│   ├── workspace.py   # Workspace management
│   ├── memory.py      # Memory/history
│   ├── brave.py       # Web search
│   ├── voice.py       # Whisper transcription
│   ├── vision.py      # Image handling
│   ├── reminders.py   # Reminder system
│   ├── documents.py   # Document parsing
│   ├── export.py      # Export functionality
│   ├── usage.py       # Cost tracking
│   ├── scheduler.py   # APScheduler wrapper
│   ├── compactor.py   # Memory compaction
│   ├── digest.py      # Daily digest
│   └── config.py      # Configuration
├── workspaces/        # Workspace directories
├── tests/             # Test suite
├── config.yaml.example
└── requirements.txt
```

## License

MIT — see [LICENSE](LICENSE)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
