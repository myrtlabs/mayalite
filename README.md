# MayaLite v0.4 — Full Featured AI Assistant

A full-featured, workspace-aware AI assistant for Telegram with web search, voice transcription, image understanding, reminders, document reading, and more.

## Features

### Core Features (from v0.3)
- **Workspace-scoped contexts** — Multiple isolated workspaces with their own memory
- **Collaborative modes** — Single user, shared-dm, or group chat
- **Long-term memory** — MEMORY.md with timestamps and auto-compaction
- **Heartbeat system** — Proactive scheduled check-ins
- **Secure** — No shell execution, sandboxed file access

### v0.4 New Features

#### 🔍 Web Search
Search the web using Brave Search API, with Claude tool_use for automatic searching.
```
/search weather in NYC
```
Claude can also automatically search when needed during conversations.

#### 🎤 Voice Messages
Send voice messages and they'll be transcribed via OpenAI Whisper, then processed as text.

#### 🖼 Image Understanding
Send photos and Claude will analyze them using vision. Add a caption to ask specific questions.

#### ⏰ Reminders
Natural language reminder parsing with persistent storage.
```
/remind in 2 hours Check the oven
/remind tomorrow at 9am Call dentist
/reminders  # List pending
```

#### 📄 Document Reading
Send PDF, TXT, or DOCX files for analysis.
```
/summarize  # Summarize last document
```
Or send with a caption to ask questions directly.

#### 📦 Export
Export your workspace data.
```
/export memory   # Export MEMORY.md
/export history  # Export chat history
/export all      # Export full workspace as zip
```

#### 🤖 Multi-Model Support
Switch between Claude models per workspace.
```
/model          # Show current model
/model sonnet   # Switch to Sonnet
/model opus     # Switch to Opus
```

#### 📊 Cost Tracking
Track token usage and estimated costs.
```
/usage        # View stats
/usage reset  # Reset counters
```

#### 🌅 Daily Digest
Configurable daily summary with weather, reminders, and memory highlights.

## Quick Start

### 1. Clone and Install

```bash
cd /path/to/maya-lite/v0.4
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys
```

Required API keys:
- **Telegram Bot Token** — From [@BotFather](https://t.me/BotFather)
- **Anthropic API Key** — From [Anthropic Console](https://console.anthropic.com)

Optional API keys:
- **Brave Search API** — For web search ([Get here](https://api.search.brave.com))
- **OpenAI API Key** — For voice transcription ([Get here](https://platform.openai.com))

### 3. Run

```bash
python main.py
```

Or with a custom config:
```bash
python main.py /path/to/config.yaml
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Full command list |
| `/status` | Workspace status and stats |
| `/clear` | Clear conversation history |
| `/remember <text>` | Save to memory |
| `/workspace [name]` | List or switch workspaces |
| `/search <query>` | Web search |
| `/remind <time> <msg>` | Set reminder |
| `/reminders` | List pending reminders |
| `/export memory\|history\|all` | Export data |
| `/model [name]` | View/change model |
| `/usage [reset]` | Token usage stats |
| `/summarize` | Summarize last document |
| `/compact [yes]` | Compact memory |
| `/catchup` | Summarize others' chats |
| `/heartbeat` | Trigger heartbeat |

## Directory Structure

```
v0.4/
├── main.py                 # Entry point
├── config.yaml             # Your configuration
├── config.yaml.example     # Template
├── requirements.txt        # Dependencies
├── src/
│   ├── __init__.py
│   ├── bot.py             # Main bot (all handlers)
│   ├── config.py          # Configuration loading
│   ├── claude.py          # Claude API client
│   ├── memory.py          # Memory management
│   ├── workspace.py       # Workspace management
│   ├── scheduler.py       # APScheduler wrapper
│   ├── compactor.py       # Memory compaction
│   ├── brave.py           # Web search
│   ├── voice.py           # Voice transcription
│   ├── vision.py          # Image understanding
│   ├── reminders.py       # Reminder system
│   ├── documents.py       # Document reading
│   ├── export.py          # Data export
│   ├── usage.py           # Cost tracking
│   └── digest.py          # Daily digest
└── workspaces/
    ├── _global/
    │   ├── IDENTITY.md    # Shared identity
    │   └── USER.md        # About the user
    └── main/
        ├── SOUL.md        # Workspace persona
        ├── MEMORY.md      # Long-term memory
        ├── TOOLS.md       # Tools reference
        ├── HEARTBEAT.md   # Heartbeat instructions
        └── history.jsonl  # Conversation history
```

## Configuration Reference

### Workspace Modes

- **single** — Default. One user, one workspace.
- **shared-dm** — Multiple users in DM, per-user history, shared memory.
- **group** — Tied to a Telegram group chat.

### Heartbeat

The heartbeat system periodically checks `HEARTBEAT.md` and sends alerts if action is needed.

```yaml
heartbeat:
  enabled: true
  interval_minutes: 30
```

### Daily Digest

Sends a daily summary at the configured time.

```yaml
digest:
  enabled: true
  time: "08:00"
  timezone: "America/New_York"
  location: "New York, NY"  # For weather
```

## Pricing Notes

Token costs are tracked per workspace in `usage.json`. Approximate costs (per 1M tokens):

| Model | Input | Output |
|-------|-------|--------|
| claude-sonnet-4 | $3 | $15 |
| claude-opus-4 | $15 | $75 |
| claude-3-5-haiku | $1 | $5 |

Voice transcription via Whisper is $0.006/minute.

## Security

- **No shell execution** — Maya cannot run arbitrary commands
- **Sandboxed file access** — Only workspace directories accessible
- **API keys in config only** — Never exposed in messages
- **User authorization** — Only listed users can interact

## Changelog

### v0.4.0
- Web search via Brave API
- Voice message transcription via Whisper
- Image understanding via Claude vision
- Natural language reminders with persistence
- Document reading (PDF, TXT, DOCX)
- Export functionality
- Multi-model support
- Cost tracking
- Daily digest

### v0.3.0
- Collaborative workspace modes
- Per-user history for shared-dm
- Group chat support
- /catchup command

### v0.2.0
- Multi-workspace support
- Heartbeat system
- Memory compaction

### v0.1.0
- Initial release
- Basic chat
- Memory persistence

## License

MIT
