# Contributing to MayaLite

## Development Setup

```bash
# Clone and setup
git clone https://github.com/pgangu/mayalite.git
cd mayalite
./mayalite setup

# Install dev dependencies
source .venv/bin/activate
pip install -e ".[dev]"
```

## Code Style

- Python 3.10+ with type hints
- Format with `ruff format`
- Lint with `ruff check`
- Type check with `mypy src/`

## Running Tests

```bash
pytest
```

## Project Structure

```
mayalite/
├── src/
│   ├── bot.py          # Telegram handlers
│   ├── claude.py       # Claude API client
│   ├── workspace.py    # Workspace management
│   ├── memory.py       # Memory/history
│   └── ...             # Feature modules
├── workspaces/         # Workspace templates
├── tests/              # Test suite
├── mayalite            # CLI script
└── config.yaml.example # Config template
```

## Security Guidelines

MayaLite is designed with security as a core principle:

1. **No shell execution** — Never add subprocess/os.system calls
2. **Sandboxed file access** — Only access workspace directories
3. **No secrets in code** — All keys in config.yaml (gitignored)
4. **Polling, not webhooks** — No open ports

## Adding Features

1. Create feature module in `src/`
2. Add config options to `config.py`
3. Wire up in `bot.py`
4. Update `config.yaml.example`
5. Add tests
6. Update CHANGELOG.md

## Pull Request Process

1. Fork the repo
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation
6. Submit PR with clear description
