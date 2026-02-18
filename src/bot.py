"""
Telegram Bot for MayaLite v0.4.

Full-featured bot with:
- v0.3: Multi-user workspaces, history, heartbeats
- v0.4: Web search, voice, vision, reminders, documents, export, multi-model, usage
"""

import asyncio
import logging
from pathlib import Path
from typing import Set, Optional, Dict, List

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from .config import Config
from .workspace import WorkspaceManager
from .memory import MemoryManager
from .claude import ClaudeClient
from .scheduler import MayaScheduler
from .compactor import MemoryCompactor
from .brave import BraveSearchClient
from .voice import VoiceTranscriber
from .vision import VisionHandler
from .reminders import ReminderManager
from .documents import DocumentReader
from .export import ExportManager
from .usage import UsageTracker
from .digest import DigestManager


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


DEFAULT_HEARTBEAT_PROMPT = """Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."""


class MayaBot:
    """
    Main bot class that ties everything together.
    """
    
    def __init__(self, config: Config, workspaces_path: Path):
        self.config = config
        self.workspaces_path = workspaces_path
        self.authorized_users: Set[int] = set(config.telegram.authorized_users)
        self.authorized_groups: Set[int] = set(config.telegram.authorized_groups)
        
        # Per-user workspace tracking
        self._user_workspaces: Dict[int, str] = {}
        
        # Per-workspace model overrides
        self._workspace_models: Dict[str, str] = {}
        
        # Initialize components
        self.workspace_manager = WorkspaceManager(
            base_path=workspaces_path,
            default_workspace=config.workspaces.default,
            workspaces_config=config.workspaces,
        )
        
        self.memory_manager = MemoryManager(
            workspace_path=self.workspace_manager.get_workspace_path(),
            history_limit=config.workspaces.history_limit,
        )
        
        # Usage tracker
        self.usage_tracker = UsageTracker(
            workspace_path=self.workspace_manager.get_workspace_path()
        )
        
        # Claude client with usage tracking
        self.claude = ClaudeClient(
            api_key=config.claude.api_key,
            model=config.models.default,
            max_tokens=config.claude.max_tokens,
            usage_callback=self.usage_tracker.record,
        )
        
        self.compactor = MemoryCompactor(claude=self.claude)
        
        # Scheduler
        self.scheduler = MayaScheduler()
        
        # Web search (optional)
        self.search_client = BraveSearchClient(config.brave.api_key) if config.brave.api_key else None
        
        # Voice transcription (optional)
        self.voice_transcriber = VoiceTranscriber(
            api_key=config.openai.api_key,
            model=config.openai.whisper_model,
        ) if config.openai.api_key else None
        
        # Vision handler
        self.vision_handler = VisionHandler()
        
        # Document reader
        self.document_reader = DocumentReader()
        
        # Pending compact confirmation
        self._pending_compact: Dict[int, str] = {}
        
        # Build application
        self.app = Application.builder().token(config.telegram.token).build()
        self._register_handlers()
        
        # Reminder manager (initialized after app is built)
        self.reminder_manager: Optional[ReminderManager] = None
        
        # Digest manager (initialized after scheduler)
        self.digest_manager: Optional[DigestManager] = None
    
    def _register_handlers(self) -> None:
        """Register command and message handlers."""
        # Basic commands
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("clear", self.cmd_clear))
        self.app.add_handler(CommandHandler("remember", self.cmd_remember))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        
        # v0.2 commands
        self.app.add_handler(CommandHandler("workspace", self.cmd_workspace))
        self.app.add_handler(CommandHandler("compact", self.cmd_compact))
        self.app.add_handler(CommandHandler("heartbeat", self.cmd_heartbeat))
        
        # v0.3 commands
        self.app.add_handler(CommandHandler("catchup", self.cmd_catchup))
        
        # v0.4 commands
        self.app.add_handler(CommandHandler("search", self.cmd_search))
        self.app.add_handler(CommandHandler("remind", self.cmd_remind))
        self.app.add_handler(CommandHandler("reminders", self.cmd_reminders))
        self.app.add_handler(CommandHandler("export", self.cmd_export))
        self.app.add_handler(CommandHandler("model", self.cmd_model))
        self.app.add_handler(CommandHandler("usage", self.cmd_usage))
        self.app.add_handler(CommandHandler("summarize", self.cmd_summarize))
        
        # Message handlers (order matters!)
        self.app.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice)
        )
        self.app.add_handler(
            MessageHandler(filters.PHOTO, self.handle_photo)
        )
        self.app.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
    
    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is globally authorized."""
        return user_id in self.authorized_users
    
    def _is_authorized_chat(self, update: Update) -> bool:
        """Check if the chat (user or group) is authorized."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Check if it's a group chat
        if self._is_group_chat(update):
            return chat_id in self.authorized_groups
        
        # For private chats, check user authorization
        return user_id in self.authorized_users
    
    def _is_group_chat(self, update: Update) -> bool:
        """Check if message is from a group chat."""
        chat_type = update.effective_chat.type
        return chat_type in ("group", "supergroup")
    
    def _get_user_workspace(self, user_id: int) -> str:
        """Get the current workspace for a user."""
        return self._user_workspaces.get(user_id, self.config.workspaces.default)
    
    def _set_user_workspace(self, user_id: int, workspace: str) -> None:
        """Set the current workspace for a user."""
        self._user_workspaces[user_id] = workspace
    
    def _get_model_for_workspace(self, workspace: str) -> str:
        """Get the model to use for a workspace."""
        # Check runtime override
        if workspace in self._workspace_models:
            return self._workspace_models[workspace]
        
        # Check workspace config
        ws_model = self.workspace_manager.get_workspace_model(workspace)
        if ws_model:
            return ws_model
        
        # Default model
        return self.config.models.default
    
    def _resolve_model_alias(self, model_name: str) -> str:
        """Resolve model alias to full model name."""
        return self.config.models.aliases.get(model_name, model_name)
    
    def _should_respond_in_group(self, update: Update, workspace: str) -> bool:
        """Determine if bot should respond to a group message."""
        listen_mode = self.workspace_manager.get_listen_mode(workspace)
        
        if listen_mode == "all":
            return True
        
        message = update.message
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mentioned = message.text[entity.offset:entity.offset + entity.length]
                    bot_username = f"@{self.app.bot.username}"
                    if mentioned.lower() == bot_username.lower():
                        return True
        
        return False
    
    def _strip_mention(self, text: str) -> str:
        """Remove @botname mention from message text."""
        if hasattr(self.app.bot, "username") and self.app.bot.username:
            bot_mention = f"@{self.app.bot.username}"
            text = text.replace(bot_mention, "").strip()
        return text
    
    def _get_memory_manager_for_workspace(self, workspace: str) -> MemoryManager:
        """Get a memory manager configured for a specific workspace."""
        workspace_path = self.workspace_manager.get_workspace_path(workspace)
        return MemoryManager(
            workspace_path=workspace_path,
            history_limit=self.config.workspaces.history_limit,
        )
    
    def _get_usage_tracker_for_workspace(self, workspace: str) -> UsageTracker:
        """Get a usage tracker for a specific workspace."""
        workspace_path = self.workspace_manager.get_workspace_path(workspace)
        return UsageTracker(workspace_path=workspace_path)
    
    def _get_export_manager_for_workspace(self, workspace: str) -> ExportManager:
        """Get an export manager for a specific workspace."""
        workspace_path = self.workspace_manager.get_workspace_path(workspace)
        return ExportManager(workspace_path=workspace_path)
    
    async def _send_message(self, chat_id: int, text: str) -> None:
        """Send a message to a chat."""
        bot = Bot(token=self.config.telegram.token)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    
    # ─────────────────────────────────────────────────────────────
    # Commands
    # ─────────────────────────────────────────────────────────────
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        logger.info(f"📩 /start from user={user_id} chat={chat_id} type={chat_type}")
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("⛔ Not authorized.")
            return
        
        await update.message.reply_text(
            "👋 Hi! I'm Maya v0.4, your AI assistant.\n\n"
            "**New in v0.4:**\n"
            "• Voice messages 🎤\n"
            "• Image understanding 🖼\n"
            "• Web search 🔍\n"
            "• Reminders ⏰\n"
            "• Document reading 📄\n"
            "• Multi-model support 🤖\n\n"
            "Use /help for all commands.",
            parse_mode="Markdown",
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        await update.message.reply_text(
            "📚 **MayaLite v0.4 Commands**\n\n"
            "**Basics**\n"
            "/clear — Clear conversation history\n"
            "/remember <text> — Save to memory\n"
            "/status — Show workspace status\n\n"
            "**Workspaces**\n"
            "/workspace — List workspaces\n"
            "/workspace <name> — Switch workspace\n\n"
            "**Search & Media (v0.4)**\n"
            "/search <query> — Web search\n"
            "/summarize — Summarize last document\n"
            "🎤 Send voice messages\n"
            "🖼 Send photos\n"
            "📄 Send documents\n\n"
            "**Reminders (v0.4)**\n"
            "/remind <time> <msg> — Set reminder\n"
            "/reminders — List pending\n\n"
            "**Export (v0.4)**\n"
            "/export memory — Export MEMORY.md\n"
            "/export history — Export chat history\n"
            "/export all — Export workspace zip\n\n"
            "**Model (v0.4)**\n"
            "/model — Show current model\n"
            "/model sonnet|opus — Switch model\n\n"
            "**Usage (v0.4)**\n"
            "/usage — Token usage stats\n"
            "/usage reset — Reset counters\n\n"
            "**Memory**\n"
            "/compact — Compact memory\n"
            "/catchup — Summarize others' chats\n"
            "/heartbeat — Trigger heartbeat",
            parse_mode="Markdown",
        )
    
    async def cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if self._is_group_chat(update):
            chat_id = update.effective_chat.id
            workspace = self.workspace_manager.get_workspace_for_group(chat_id)
            if not workspace:
                await update.message.reply_text("❌ This group is not linked to a workspace.")
                return
            memory = self._get_memory_manager_for_workspace(workspace)
            memory.clear_history()
        else:
            workspace = self._get_user_workspace(user_id)
            mode = self.workspace_manager.get_workspace_mode(workspace)
            memory = self._get_memory_manager_for_workspace(workspace)
            
            if mode == "shared-dm":
                memory.clear_history(user_id=user_id)
            else:
                memory.clear_history()
        
        await update.message.reply_text("🧹 Conversation history cleared.")
    
    async def cmd_remember(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remember command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        text = " ".join(context.args) if context.args else ""
        
        if not text:
            await update.message.reply_text("Usage: /remember <text to save>")
            return
        
        if self._is_group_chat(update):
            chat_id = update.effective_chat.id
            workspace = self.workspace_manager.get_workspace_for_group(chat_id)
            if not workspace:
                await update.message.reply_text("❌ This group is not linked.")
                return
        else:
            workspace = self._get_user_workspace(user_id)
        
        memory = self._get_memory_manager_for_workspace(workspace)
        
        if memory.append_memory(text):
            await update.message.reply_text("💾 Saved to memory.")
        else:
            await update.message.reply_text("❌ Failed to save.")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if self._is_group_chat(update):
            chat_id = update.effective_chat.id
            workspace = self.workspace_manager.get_workspace_for_group(chat_id)
            if not workspace:
                await update.message.reply_text("❌ This group is not linked.")
                return
        else:
            workspace = self._get_user_workspace(user_id)
        
        mode = self.workspace_manager.get_workspace_mode(workspace)
        memory = self._get_memory_manager_for_workspace(workspace)
        model = self._get_model_for_workspace(workspace)
        
        if mode == "shared-dm":
            history_stats = memory.get_history_stats(user_id=user_id)
        else:
            history_stats = memory.get_history_stats()
        
        memory_stats = memory.get_memory_stats()
        usage = self._get_usage_tracker_for_workspace(workspace)
        usage_stats = usage.get_stats()
        
        if not self._is_group_chat(update):
            available = self.workspace_manager.get_authorized_workspaces(user_id)
        else:
            available = [workspace]
        
        scheduler_status = "🟢 Running" if self.scheduler.is_running() else "⚪ Stopped"
        mode_emoji = {"single": "👤", "shared-dm": "👥", "group": "💬"}.get(mode, "❓")
        
        # Shorten model name
        short_model = model.split("-")[1] if "-" in model else model
        
        status = [
            f"📊 **Status**\n",
            f"**Workspace:** `{workspace}` {mode_emoji}",
            f"**Model:** {short_model}",
            f"**History:** {history_stats['turns']} turns",
            f"**Memory:** {memory_stats.get('sections', 0)} sections",
            f"**Usage:** {usage_stats['total_requests']} reqs, ${usage_stats['total_cost']:.4f}",
            f"**Scheduler:** {scheduler_status}",
        ]
        
        await update.message.reply_text("\n".join(status), parse_mode="Markdown")
    
    async def cmd_workspace(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /workspace command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if self._is_group_chat(update):
            chat_id = update.effective_chat.id
            workspace = self.workspace_manager.get_workspace_for_group(chat_id)
            if workspace:
                await update.message.reply_text(
                    f"💬 **Group Workspace:** `{workspace}`",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("❌ This group is not linked.")
            return
        
        args = context.args
        current = self._get_user_workspace(user_id)
        available = self.workspace_manager.get_authorized_workspaces(user_id)
        
        if not args:
            ws_list = []
            for ws in available:
                info = self.workspace_manager.get_workspace_info(ws)
                marker = "→ " if ws == current else "  "
                mode = info.get("mode", "single")
                mode_emoji = {"single": "👤", "shared-dm": "👥", "group": "💬"}.get(mode, "")
                ws_list.append(f"{marker}`{ws}` {mode_emoji}")
            
            await update.message.reply_text(
                f"🗂 **Workspaces**\n\nCurrent: `{current}`\n\n" +
                "\n".join(ws_list) +
                "\n\nUse `/workspace <name>` to switch",
                parse_mode="Markdown",
            )
        else:
            target = args[0].lower()
            
            if target == current:
                await update.message.reply_text(f"Already in `{current}`", parse_mode="Markdown")
                return
            
            if target not in available:
                await update.message.reply_text(f"❌ Not authorized for `{target}`", parse_mode="Markdown")
                return
            
            if self.workspace_manager.workspace_exists(target):
                self._set_user_workspace(user_id, target)
                await update.message.reply_text(f"✅ Switched to `{target}`", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ Workspace `{target}` not found", parse_mode="Markdown")
    
    async def cmd_compact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /compact command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if self._is_group_chat(update):
            chat_id = update.effective_chat.id
            workspace = self.workspace_manager.get_workspace_for_group(chat_id)
            if not workspace:
                await update.message.reply_text("❌ Not linked.")
                return
        else:
            workspace = self._get_user_workspace(user_id)
        
        memory = self._get_memory_manager_for_workspace(workspace)
        args = context.args
        
        if args and args[0].lower() == "yes":
            if user_id not in self._pending_compact:
                await update.message.reply_text("No pending compaction. Run /compact first.")
                return
            
            await update.message.reply_text("⏳ Compacting memory...")
            success, message = self.compactor.compact(memory, dry_run=False)
            del self._pending_compact[user_id]
            
            if success:
                await update.message.reply_text(f"✅ {message}")
            else:
                await update.message.reply_text(f"❌ {message}")
            return
        
        await update.message.reply_text("⏳ Generating preview...")
        success, preview = self.compactor.preview(memory)
        
        if not success:
            await update.message.reply_text(f"❌ {preview}")
            return
        
        self._pending_compact[user_id] = preview
        
        if len(preview) > 3500:
            preview = preview[:3500] + "\n\n... (truncated)"
        
        await update.message.reply_text(
            f"📋 **Preview**\n\n{preview}\n\n`/compact yes` to apply",
            parse_mode="Markdown",
        )
    
    async def cmd_heartbeat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /heartbeat command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if not self.config.heartbeat.enabled:
            await update.message.reply_text("💔 Heartbeat disabled.")
            return
        
        await update.message.reply_text("💓 Triggering heartbeat...")
        await self._run_heartbeat()
    
    async def cmd_catchup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /catchup command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if self._is_group_chat(update):
            await update.message.reply_text("ℹ️ /catchup is for shared-dm workspaces.")
            return
        
        workspace = self._get_user_workspace(user_id)
        mode = self.workspace_manager.get_workspace_mode(workspace)
        
        if mode != "shared-dm":
            await update.message.reply_text(f"ℹ️ Workspace `{workspace}` is `{mode}` mode.", parse_mode="Markdown")
            return
        
        authorized_users = self.workspace_manager.get_workspace_authorized_users(workspace)
        
        if len(authorized_users) <= 1:
            await update.message.reply_text("👤 You're the only user.")
            return
        
        memory = self._get_memory_manager_for_workspace(workspace)
        other_history = memory.load_other_users_history(user_id, authorized_users, limit=50)
        
        if not other_history:
            await update.message.reply_text("📭 No recent conversations from others.")
            return
        
        await update.message.reply_text("⏳ Summarizing...")
        
        catchup_prompt = memory.get_catchup_summary_prompt(other_history)
        system_prompt = "You are Maya. Summarize the following conversations concisely."
        
        try:
            summary = self.claude.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": catchup_prompt}],
                max_tokens=1024,
            )
            await update.message.reply_text(f"📋 **Catchup**\n\n{summary}", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
    
    # ─────────────────────────────────────────────────────────────
    # v0.4 Commands
    # ─────────────────────────────────────────────────────────────
    
    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /search command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if not self.search_client or not self.search_client.enabled:
            await update.message.reply_text("🔍 Search not configured. Add `brave.api_key` to config.")
            return
        
        query = " ".join(context.args) if context.args else ""
        
        if not query:
            await update.message.reply_text("Usage: /search <query>")
            return
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            results = await self.search_client.search_formatted(query)
            await update.message.reply_text(results, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Search error: {str(e)[:200]}")
    
    async def cmd_remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remind command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if not self.reminder_manager:
            await update.message.reply_text("❌ Reminders not initialized.")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /remind <time> <message>\n\n"
                "Examples:\n"
                "• /remind in 2 hours Check email\n"
                "• /remind tomorrow at 9am Meeting\n"
                "• /remind in 30 minutes Call back"
            )
            return
        
        # Parse time - try to find the message part
        full_text = " ".join(context.args)
        
        # Common time patterns
        time_keywords = ["in", "at", "tomorrow", "next", "on"]
        
        # Find where message starts (after time expression)
        parts = full_text.split()
        message_start = len(parts)
        
        for i, part in enumerate(parts):
            # If we find a word that's likely the start of a message
            if i > 0 and part[0].isupper() and part.lower() not in time_keywords:
                message_start = i
                break
        
        # Split into time and message
        if message_start > 0 and message_start < len(parts):
            time_str = " ".join(parts[:message_start])
            message = " ".join(parts[message_start:])
        else:
            # Fallback: first 3 words are time
            time_str = " ".join(parts[:3])
            message = " ".join(parts[3:]) or "Reminder"
        
        workspace = self._get_user_workspace(user_id)
        
        reminder = self.reminder_manager.create_reminder(
            user_id=user_id,
            chat_id=update.effective_chat.id,
            time_str=time_str,
            message=message,
            workspace=workspace,
        )
        
        if reminder:
            from datetime import datetime
            trigger = datetime.fromisoformat(reminder.trigger_time)
            await update.message.reply_text(
                f"⏰ Reminder set!\n\n"
                f"**Message:** {message}\n"
                f"**When:** {trigger.strftime('%Y-%m-%d %H:%M %Z')}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("❌ Couldn't parse time. Try: 'in 2 hours', 'tomorrow at 9am'")
    
    async def cmd_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reminders command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if not self.reminder_manager:
            await update.message.reply_text("❌ Reminders not initialized.")
            return
        
        workspace = self._get_user_workspace(user_id)
        reminders = self.reminder_manager.list_reminders(user_id=user_id, workspace=workspace)
        
        await update.message.reply_text(
            self.reminder_manager.format_reminder_list(reminders),
            parse_mode="Markdown",
        )
    
    async def cmd_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /export command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        workspace = self._get_user_workspace(user_id)
        export_mgr = self._get_export_manager_for_workspace(workspace)
        
        if not context.args:
            info = export_mgr.list_exportable()
            await update.message.reply_text(
                f"📦 **Export Options**\n\n"
                f"Memory: {'✅' if info['memory'] else '❌'}\n"
                f"History: {info['history_turns']} turns\n"
                f"Reminders: {info['reminders']}\n\n"
                "Usage:\n"
                "`/export memory` — MEMORY.md\n"
                "`/export history` — Chat history\n"
                "`/export all` — Full workspace zip",
                parse_mode="Markdown",
            )
            return
        
        export_type = context.args[0].lower()
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
        
        try:
            if export_type == "memory":
                path = export_mgr.export_memory()
                if not path:
                    await update.message.reply_text("❌ No memory to export.")
                    return
            elif export_type == "history":
                path = export_mgr.export_history(user_id=user_id)
                if not path:
                    await update.message.reply_text("❌ No history to export.")
                    return
            elif export_type == "all":
                path = export_mgr.export_all()
                if not path:
                    await update.message.reply_text("❌ Nothing to export.")
                    return
            else:
                await update.message.reply_text("Usage: /export memory|history|all")
                return
            
            await update.message.reply_document(
                document=open(path, "rb"),
                filename=path.name,
                caption=f"📦 Exported: {path.name}",
            )
            
            # Clean up temp file
            path.unlink()
            
        except Exception as e:
            await update.message.reply_text(f"❌ Export error: {str(e)[:200]}")
    
    async def cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /model command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        workspace = self._get_user_workspace(user_id)
        current_model = self._get_model_for_workspace(workspace)
        
        if not context.args:
            # Show current model and available aliases
            aliases = self.config.models.aliases
            alias_list = "\n".join([f"• `{k}` → {v.split('-')[1]}" for k, v in aliases.items()])
            
            await update.message.reply_text(
                f"🤖 **Model**\n\n"
                f"Current: `{current_model.split('-')[1] if '-' in current_model else current_model}`\n"
                f"Full: `{current_model}`\n\n"
                f"**Available:**\n{alias_list}\n\n"
                f"Use `/model <name>` to switch",
                parse_mode="Markdown",
            )
            return
        
        model_name = context.args[0].lower()
        resolved = self._resolve_model_alias(model_name)
        
        self._workspace_models[workspace] = resolved
        
        # Update Claude client for immediate effect
        self.claude.set_model(resolved)
        
        short_name = resolved.split("-")[1] if "-" in resolved else resolved
        await update.message.reply_text(
            f"✅ Model switched to `{short_name}` for workspace `{workspace}`",
            parse_mode="Markdown",
        )
    
    async def cmd_usage(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /usage command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        workspace = self._get_user_workspace(user_id)
        usage = self._get_usage_tracker_for_workspace(workspace)
        
        if context.args and context.args[0].lower() == "reset":
            usage.reset()
            await update.message.reply_text("🔄 Usage statistics reset.")
            return
        
        await update.message.reply_text(usage.format_stats(), parse_mode="Markdown")
    
    async def cmd_summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /summarize command - summarize last document."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        workspace = self._get_user_workspace(user_id)
        memory = self._get_memory_manager_for_workspace(workspace)
        
        doc = memory.get_last_document(user_id=user_id)
        
        if not doc:
            await update.message.reply_text("❌ No document to summarize. Send a PDF, TXT, or DOCX first.")
            return
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            # Set model for this workspace
            model = self._get_model_for_workspace(workspace)
            self.claude.set_model(model)
            
            prompt = f"Please summarize the following document ({doc['filename']}):\n\n{doc['text']}"
            
            response = self.claude.chat(
                system="You are Maya. Provide a concise summary of the document.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            
            await update.message.reply_text(
                f"📄 **Summary of {doc['filename']}**\n\n{response}",
                parse_mode="Markdown",
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
    
    # ─────────────────────────────────────────────────────────────
    # Message Handlers
    # ─────────────────────────────────────────────────────────────
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice messages."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        if not self.voice_transcriber or not self.voice_transcriber.enabled:
            await update.message.reply_text("🎤 Voice not configured. Add `openai.api_key` to config.")
            return
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            # Get voice file
            voice = update.message.voice or update.message.audio
            if not voice:
                return
            
            # Transcribe
            transcript = await self.voice_transcriber.transcribe_telegram_voice(
                context.bot,
                voice.file_id,
            )
            
            if not transcript:
                await update.message.reply_text("❌ Couldn't transcribe voice message.")
                return
            
            # Show transcription
            await update.message.reply_text(f"🎤 *Transcribed:* {transcript}", parse_mode="Markdown")
            
            # Process as regular message
            fake_update = update
            fake_update.message.text = transcript
            await self.handle_message(fake_update, context)
            
        except Exception as e:
            logger.error(f"Voice error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Voice error: {str(e)[:200]}")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo messages."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            # Get best photo size
            photo = self.vision_handler.get_best_photo_size(update.message.photo)
            
            # Download photo
            image_bytes, mime_type = await self.vision_handler.download_telegram_photo(
                context.bot,
                photo.file_id,
            )
            
            # Get caption
            caption = update.message.caption or "What's in this image?"
            
            # Build vision message
            content = self.vision_handler.build_image_content(image_bytes, mime_type, caption)
            
            # Determine workspace and model
            workspace = self._get_user_workspace(user_id)
            model = self._get_model_for_workspace(workspace)
            self.claude.set_model(model)
            
            # Get system prompt
            original = self.workspace_manager.current
            self.workspace_manager.current = workspace
            system_prompt = self.workspace_manager.load_context()
            self.workspace_manager.current = original
            
            # Send to Claude
            response = self.claude.chat_with_vision(
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
            )
            
            await self._send_response(update, response)
            
        except Exception as e:
            logger.error(f"Photo error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Photo error: {str(e)[:200]}")
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document attachments."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        document = update.message.document
        if not document:
            return
        
        # Check if we support this type
        doc_type = self.document_reader.detect_type(
            document.file_name or "",
            document.mime_type or "",
        )
        
        if not doc_type:
            await update.message.reply_text(
                "📄 Unsupported document type. I can read: PDF, TXT, DOCX"
            )
            return
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            # Read and extract
            text, filename = await self.document_reader.read_and_extract(
                context.bot,
                document,
            )
            
            # Save for /summarize
            workspace = self._get_user_workspace(user_id)
            memory = self._get_memory_manager_for_workspace(workspace)
            memory.save_last_document(filename, text, user_id)
            
            # If caption provided, process with document context
            caption = update.message.caption
            
            if caption:
                # Process with document context
                model = self._get_model_for_workspace(workspace)
                self.claude.set_model(model)
                
                prompt = f"Document: {filename}\n\nContent:\n{text[:50000]}\n\nUser question: {caption}"
                
                original = self.workspace_manager.current
                self.workspace_manager.current = workspace
                system_prompt = self.workspace_manager.load_context()
                self.workspace_manager.current = original
                
                response = self.claude.chat(
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                
                await self._send_response(update, response)
            else:
                # Just acknowledge
                await update.message.reply_text(
                    f"📄 **{filename}** received ({len(text):,} chars)\n\n"
                    f"Use /summarize to get a summary, or ask me questions about it.",
                    parse_mode="Markdown",
                )
            
        except Exception as e:
            logger.error(f"Document error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Document error: {str(e)[:200]}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        logger.info(f"📩 Message from user={user_id} chat={chat_id} type={chat_type}")
        
        if not self._is_authorized_chat(update):
            logger.warning(f"Unauthorized: user={user_id} chat={chat_id}")
            # Only reply in private chats
            if not self._is_group_chat(update):
                await update.message.reply_text("⛔ Not authorized.")
            return
        
        # Determine workspace and mode
        if self._is_group_chat(update):
            chat_id = update.effective_chat.id
            workspace = self.workspace_manager.get_workspace_for_group(chat_id)
            
            if not workspace:
                return
            
            if not self._should_respond_in_group(update, workspace):
                return
            
            mode = "group"
            user_message = self._strip_mention(update.message.text)
        else:
            workspace = self._get_user_workspace(user_id)
            mode = self.workspace_manager.get_workspace_mode(workspace)
            
            if mode == "shared-dm":
                if not self.workspace_manager.is_user_authorized(workspace, user_id):
                    await update.message.reply_text(f"⛔ Not authorized for `{workspace}`.", parse_mode="Markdown")
                    return
            
            user_message = update.message.text
        
        # Clear pending compact
        if user_id in self._pending_compact:
            del self._pending_compact[user_id]
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            # Set model for workspace
            model = self._get_model_for_workspace(workspace)
            self.claude.set_model(model)
            
            # Update usage tracker for workspace
            usage = self._get_usage_tracker_for_workspace(workspace)
            self.claude.set_usage_callback(usage.record)
            
            memory = self._get_memory_manager_for_workspace(workspace)
            
            original_workspace = self.workspace_manager.current
            self.workspace_manager.current = workspace
            system_prompt = self.workspace_manager.load_context()
            self.workspace_manager.current = original_workspace
            
            if mode == "shared-dm":
                history = memory.load_history(user_id=user_id)
            else:
                history = memory.load_history()
            
            messages = history + [{"role": "user", "content": user_message}]
            
            # Check if we should use tools (web search)
            tools = []
            if self.search_client and self.search_client.enabled:
                tools.append(self.search_client.get_tool_definition())
            
            if tools:
                # Use tool-enabled chat
                def tool_handler(name: str, input_data: dict) -> str:
                    if name == "web_search":
                        # Use sync search method to avoid event loop issues
                        result = self.search_client.search_sync(
                            query=input_data.get("query", ""),
                            count=input_data.get("count", 5),
                        )
                        return self.search_client.format_for_claude(result)
                    return f"Unknown tool: {name}"
                
                response = self.claude.chat_with_tools(
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                    tool_handler=tool_handler,
                )
            else:
                response = self.claude.chat(system=system_prompt, messages=messages)
            
            # Save history
            if mode == "shared-dm":
                memory.append_turn("user", user_message, user_id=user_id)
                memory.append_turn("assistant", response, user_id=user_id)
            else:
                memory.append_turn("user", user_message)
                memory.append_turn("assistant", response)
            
            await self._send_response(update, response)
            
        except Exception as e:
            logger.error(f"Message error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
    
    async def _send_response(self, update: Update, response: str) -> None:
        """Send response, splitting if necessary."""
        MAX_LENGTH = 4000
        
        if len(response) <= MAX_LENGTH:
            await update.message.reply_text(response)
        else:
            chunks = [response[i:i + MAX_LENGTH] for i in range(0, len(response), MAX_LENGTH)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
    
    # ─────────────────────────────────────────────────────────────
    # Heartbeat
    # ─────────────────────────────────────────────────────────────
    
    async def _run_heartbeat(self) -> None:
        """Execute a heartbeat cycle."""
        try:
            heartbeat_content = self.workspace_manager.load_heartbeat_prompt()
            
            if heartbeat_content:
                prompt = f"HEARTBEAT.md:\n\n{heartbeat_content}\n\n{DEFAULT_HEARTBEAT_PROMPT}"
            else:
                prompt = DEFAULT_HEARTBEAT_PROMPT
            
            system_prompt = self.workspace_manager.load_context()
            
            response = self.claude.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            
            if "HEARTBEAT_OK" in response:
                logger.info("Heartbeat OK")
                return
            
            alert_chat_id = self.config.telegram.alert_chat_id
            if not alert_chat_id and self.authorized_users:
                alert_chat_id = next(iter(self.authorized_users))
            
            if alert_chat_id:
                await self._send_message(
                    alert_chat_id,
                    f"💓 **Heartbeat Alert**\n\n{response[:3500]}",
                )
            
        except Exception as e:
            logger.error(f"Heartbeat error: {e}", exc_info=True)
    
    async def _run_scheduled_compaction(self) -> None:
        """Execute scheduled memory compaction."""
        try:
            success, message = self.compactor.compact(self.memory_manager, dry_run=False)
            logger.info(f"Scheduled compaction: {message}")
        except Exception as e:
            logger.error(f"Compaction error: {e}", exc_info=True)
    
    def _setup_scheduler(self) -> None:
        """Configure and start the scheduler."""
        if self.config.heartbeat.enabled:
            self.scheduler.setup_heartbeat(
                callback=self._run_heartbeat,
                interval_minutes=self.config.heartbeat.interval_minutes,
            )
        
        if self.config.heartbeat.compact_enabled:
            self.scheduler.setup_compaction(
                callback=self._run_scheduled_compaction,
                cron_expression=self.config.heartbeat.compact_cron,
            )
        
        # Initialize reminder manager with scheduler
        default_workspace = self.workspace_manager.get_workspace_path()
        self.reminder_manager = ReminderManager(
            workspace_path=default_workspace,
            scheduler=self.scheduler.get_scheduler(),
            send_callback=self._send_message,
        )
        
        # Initialize digest manager
        if self.config.digest.enabled:
            self.digest_manager = DigestManager(
                config=self.config.digest,
                scheduler=self.scheduler.get_scheduler(),
                send_callback=self._send_message,
                reminder_manager=self.reminder_manager,
                memory_reader=self.memory_manager.read_memory,
            )
            
            # Add alert chat as digest recipient
            if self.config.telegram.alert_chat_id:
                self.digest_manager.add_recipient(self.config.telegram.alert_chat_id)
        
        if self.config.heartbeat.enabled or self.config.heartbeat.compact_enabled or self.config.digest.enabled:
            self.scheduler.start()
    
    def run(self) -> None:
        """Start the bot."""
        logger.info("Starting MayaLite v0.4...")
        logger.info(f"Default workspace: {self.config.workspaces.default}")
        logger.info(f"Authorized users: {self.authorized_users}")
        logger.info(f"Search: {'✅' if self.search_client and self.search_client.enabled else '❌'}")
        logger.info(f"Voice: {'✅' if self.voice_transcriber and self.voice_transcriber.enabled else '❌'}")
        logger.info(f"Digest: {'✅' if self.config.digest.enabled else '❌'}")
        
        self._setup_scheduler()
        
        try:
            self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        finally:
            self.scheduler.stop()
