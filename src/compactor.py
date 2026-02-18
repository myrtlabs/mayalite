"""
Memory Compactor for MayaLite v0.4.

Uses Claude to consolidate and clean up MEMORY.md files.
"""

import logging
from typing import Tuple

from .claude import ClaudeClient
from .memory import MemoryManager

logger = logging.getLogger(__name__)

# Prompt for memory compaction
COMPACT_PROMPT = """You are a memory consolidation assistant. Your task is to consolidate the following memory log.

INSTRUCTIONS:
1. Remove duplicate information
2. Organize entries by topic/theme
3. Drop stale or outdated items that are no longer relevant
4. Keep it concise but complete - don't lose important information
5. Maintain a clean markdown format with headers and sections
6. If dates are relevant, keep the most recent ones
7. Preserve any persistent facts, preferences, or important context

CURRENT MEMORY LOG:
---
{memory}
---

OUTPUT FORMAT:
Return ONLY the consolidated memory content in markdown format. Do not include any preamble or explanation - just the cleaned up memory content."""

COMPACT_SYSTEM_PROMPT = """You are a precise text processing assistant. Your only job is to consolidate and clean up memory logs. Output only the processed content, nothing else."""


class MemoryCompactor:
    """
    Handles memory compaction using Claude.
    """
    
    def __init__(self, claude: ClaudeClient):
        self.claude = claude
    
    def generate_compacted_memory(self, memory_content: str) -> str:
        """Generate compacted memory content using Claude."""
        prompt = COMPACT_PROMPT.format(memory=memory_content)
        
        response = self.claude.chat(
            system=COMPACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        
        return response.strip()
    
    def compact(
        self,
        memory_manager: MemoryManager,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """
        Perform memory compaction.
        
        Args:
            memory_manager: MemoryManager instance
            dry_run: If True, returns preview without writing
            
        Returns:
            Tuple of (success: bool, message/preview: str)
        """
        current_memory = memory_manager.read_memory()
        
        if not current_memory:
            return False, "No memory to compact"
        
        if len(current_memory.strip()) < 500:
            return False, "Memory too small to compact"
        
        try:
            compacted = self.generate_compacted_memory(current_memory)
            
            if not compacted:
                return False, "Compaction returned empty result"
            
            if dry_run:
                stats = f"Original: {len(current_memory)} chars → Compacted: {len(compacted)} chars"
                reduction = (1 - len(compacted) / len(current_memory)) * 100
                return True, f"{stats} ({reduction:.1f}% reduction)\n\n---\n\n{compacted}"
            
            if not memory_manager.backup_memory():
                return False, "Failed to backup memory"
            
            if not memory_manager.write_memory(compacted):
                memory_manager.restore_memory_from_backup()
                return False, "Failed to write compacted memory"
            
            reduction = (1 - len(compacted) / len(current_memory)) * 100
            return True, f"Memory compacted ({reduction:.1f}% reduction). Backup saved to MEMORY.md.bak"
            
        except Exception as e:
            logger.error(f"Compaction error: {e}", exc_info=True)
            return False, f"Compaction failed: {str(e)}"
    
    def preview(self, memory_manager: MemoryManager) -> Tuple[bool, str]:
        """Preview compaction without applying."""
        return self.compact(memory_manager, dry_run=True)
