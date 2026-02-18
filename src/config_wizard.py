#!/usr/bin/env python3
"""
MayaLite Configuration Wizard
Interactive setup for API keys and settings.
"""

import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"
EXAMPLE_FILE = Path(__file__).parent.parent / "config.yaml.example"

# ANSI colors
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
DIM = "\033[2m"
NC = "\033[0m"  # No Color


def mask_value(value: str, show_chars: int = 4) -> str:
    """Mask a secret value, showing only last N chars."""
    if not value or len(value) <= show_chars:
        return "***"
    return "•" * 8 + value[-show_chars:]


def prompt(label: str, current: str = "", required: bool = False, secret: bool = False) -> str:
    """
    Prompt user for input with optional current value.
    - Empty input keeps current value
    - For required fields with no current, keeps prompting
    """
    if current and secret:
        display_current = mask_value(current)
    else:
        display_current = current or "(not set)"
    
    hint = f"{DIM}[{display_current}]{NC}" if current else f"{DIM}[skip]{NC}" if not required else ""
    
    while True:
        try:
            user_input = input(f"{CYAN}{label}{NC} {hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            sys.exit(1)
        
        if user_input:
            return user_input
        elif current:
            return current
        elif not required:
            return ""
        else:
            print(f"  {YELLOW}This field is required.{NC}")


def run_wizard():
    """Run the interactive configuration wizard."""
    print()
    print(f"{BLUE}╔══════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║     MayaLite Configuration Wizard        ║{NC}")
    print(f"{BLUE}╚══════════════════════════════════════════╝{NC}")
    print()
    print(f"{DIM}Press Enter to keep current value, or type new value.{NC}")
    print(f"{DIM}Leave optional fields blank to skip.{NC}")
    print()

    # Load existing config or example
    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f) or {}
        print(f"{GREEN}✓ Found existing config.yaml{NC}")
    elif EXAMPLE_FILE.exists():
        with open(EXAMPLE_FILE) as f:
            config = yaml.safe_load(f) or {}
        print(f"{YELLOW}Using config.yaml.example as base{NC}")
    
    print()
    
    # Ensure nested dicts exist
    config.setdefault("telegram", {})
    config.setdefault("claude", {})
    config.setdefault("brave", {})
    config.setdefault("openai", {})
    config.setdefault("workspaces", {"default": "main", "history_limit": 20})
    
    # ─────────────────────────────────────────
    # Telegram
    # ─────────────────────────────────────────
    print(f"{BLUE}═══ Telegram ═══{NC}")
    
    current_token = config["telegram"].get("token", "")
    if current_token and "YOUR_" in current_token:
        current_token = ""
    config["telegram"]["token"] = prompt(
        "Bot Token (from @BotFather)", 
        current_token, 
        required=True, 
        secret=True
    )
    
    # Authorized users
    current_users = config["telegram"].get("authorized_users", [])
    if current_users and current_users != [123456789]:
        current_str = ",".join(str(u) for u in current_users)
    else:
        current_str = ""
    
    users_input = prompt(
        "Your Telegram User ID (comma-separated for multiple)",
        current_str,
        required=True
    )
    config["telegram"]["authorized_users"] = [
        int(u.strip()) for u in users_input.split(",") if u.strip().isdigit()
    ]
    
    # Alert chat ID (optional, defaults to first user)
    current_alert = config["telegram"].get("alert_chat_id", "")
    if not current_alert or current_alert == 123456789:
        current_alert = config["telegram"]["authorized_users"][0] if config["telegram"]["authorized_users"] else ""
    
    alert_input = prompt(
        "Alert Chat ID (for notifications, default: your user ID)",
        str(current_alert) if current_alert else ""
    )
    config["telegram"]["alert_chat_id"] = int(alert_input) if alert_input else config["telegram"]["authorized_users"][0]
    
    print()
    
    # ─────────────────────────────────────────
    # Claude
    # ─────────────────────────────────────────
    print(f"{BLUE}═══ Claude AI ═══{NC}")
    print(f"{DIM}Accepts API key (sk-ant-api03-...) or OAuth token (sk-ant-oat01-...){NC}")
    
    current_claude = config["claude"].get("api_key", "")
    if current_claude and "YOUR_" in current_claude:
        current_claude = ""
    config["claude"]["api_key"] = prompt(
        "Anthropic API Key or OAuth Token",
        current_claude,
        required=True,
        secret=True
    )
    
    # Model (optional, has sensible default)
    current_model = config["claude"].get("model", "claude-sonnet-4-20250514")
    config["claude"]["model"] = prompt(
        "Default model",
        current_model
    ) or current_model
    
    print()
    
    # ─────────────────────────────────────────
    # Optional: Brave Search
    # ─────────────────────────────────────────
    print(f"{BLUE}═══ Web Search (optional) ═══{NC}")
    
    current_brave = config["brave"].get("api_key", "")
    if current_brave and "YOUR_" in current_brave:
        current_brave = ""
    config["brave"]["api_key"] = prompt(
        "Brave Search API Key",
        current_brave,
        secret=True
    )
    
    print()
    
    # ─────────────────────────────────────────
    # Optional: OpenAI (Whisper)
    # ─────────────────────────────────────────
    print(f"{BLUE}═══ Voice Transcription (optional) ═══{NC}")
    
    current_openai = config["openai"].get("api_key", "")
    if current_openai and "YOUR_" in current_openai:
        current_openai = ""
    config["openai"]["api_key"] = prompt(
        "OpenAI API Key (for Whisper)",
        current_openai,
        secret=True
    )
    config["openai"]["whisper_model"] = "whisper-1"
    
    print()
    
    # ─────────────────────────────────────────
    # Write config
    # ─────────────────────────────────────────
    print(f"{YELLOW}Writing config.yaml...{NC}")
    
    # Preserve any extra config sections
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print()
    print(f"{GREEN}✅ Configuration saved!{NC}")
    print()
    print(f"Config file: {CONFIG_FILE}")
    print()
    print("Next steps:")
    print(f"  {CYAN}./mayalite start{NC}  - Start MayaLite")
    print(f"  {CYAN}./mayalite config{NC} - Edit config anytime")
    print()


if __name__ == "__main__":
    run_wizard()
