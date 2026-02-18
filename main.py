#!/usr/bin/env python3
"""
MayaLite v0.4 - Entry Point

A full-featured AI assistant with workspace-scoped contexts.
"""

import sys
from pathlib import Path

from src.config import load_config
from src.bot import MayaBot


def main():
    """Main entry point."""
    # Determine paths
    project_root = Path(__file__).parent.resolve()
    workspaces_path = project_root / "workspaces"
    
    # Allow config path override via command line
    config_path = None
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])
    
    try:
        # Load configuration
        config = load_config(config_path)
        
        # Create and run bot
        bot = MayaBot(config=config, workspaces_path=workspaces_path)
        bot.run()
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
