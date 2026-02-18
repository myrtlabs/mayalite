"""
Cost tracking for MayaLite v0.4.

Track token usage and estimated costs per model.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


# Token pricing per 1M tokens (as of early 2025)
# Format: (input_price, output_price)
MODEL_PRICING = {
    # Claude 4 models
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-opus-4-20250514": (15.0, 75.0),
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (1.0, 5.0),
    # Fallback for unknown models
    "default": (3.0, 15.0),
}


@dataclass
class UsageRecord:
    """Usage record for a single request."""
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: str


@dataclass
class UsageStats:
    """Aggregate usage statistics."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0
    by_model: Dict[str, Dict[str, int]] = None
    first_request: Optional[str] = None
    last_request: Optional[str] = None
    
    def __post_init__(self):
        if self.by_model is None:
            self.by_model = {}


class UsageTracker:
    """
    Tracks token usage and costs.
    
    Stores usage in workspace/usage.json.
    """
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._stats: UsageStats = UsageStats()
        self._load()
    
    @property
    def usage_file(self) -> Path:
        return self.workspace_path / "usage.json"
    
    def _load(self) -> None:
        """Load usage data from file."""
        if not self.usage_file.exists():
            return
        
        try:
            with open(self.usage_file, "r") as f:
                data = json.load(f)
            
            self._stats = UsageStats(
                total_input_tokens=data.get("total_input_tokens", 0),
                total_output_tokens=data.get("total_output_tokens", 0),
                total_requests=data.get("total_requests", 0),
                by_model=data.get("by_model", {}),
                first_request=data.get("first_request"),
                last_request=data.get("last_request"),
            )
            
        except Exception as e:
            logger.error(f"Error loading usage data: {e}")
    
    def _save(self) -> None:
        """Save usage data to file."""
        try:
            self.workspace_path.mkdir(parents=True, exist_ok=True)
            
            data = {
                "total_input_tokens": self._stats.total_input_tokens,
                "total_output_tokens": self._stats.total_output_tokens,
                "total_requests": self._stats.total_requests,
                "by_model": self._stats.by_model,
                "first_request": self._stats.first_request,
                "last_request": self._stats.last_request,
            }
            
            with open(self.usage_file, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")
    
    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """
        Record a usage event.
        
        Args:
            model: Model name used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Update totals
        self._stats.total_input_tokens += input_tokens
        self._stats.total_output_tokens += output_tokens
        self._stats.total_requests += 1
        
        # Update timestamps
        if not self._stats.first_request:
            self._stats.first_request = now
        self._stats.last_request = now
        
        # Update per-model stats
        if model not in self._stats.by_model:
            self._stats.by_model[model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "requests": 0,
            }
        
        self._stats.by_model[model]["input_tokens"] += input_tokens
        self._stats.by_model[model]["output_tokens"] += output_tokens
        self._stats.by_model[model]["requests"] += 1
        
        # Save
        self._save()
    
    def get_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for tokens.
        
        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        input_price, output_price = pricing
        
        # Prices are per 1M tokens
        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price
        
        return input_cost + output_cost
    
    def get_total_cost(self) -> float:
        """Get total estimated cost across all models."""
        total = 0.0
        
        for model, stats in self._stats.by_model.items():
            total += self.get_cost(
                model,
                stats["input_tokens"],
                stats["output_tokens"]
            )
        
        return total
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_input_tokens": self._stats.total_input_tokens,
            "total_output_tokens": self._stats.total_output_tokens,
            "total_tokens": self._stats.total_input_tokens + self._stats.total_output_tokens,
            "total_requests": self._stats.total_requests,
            "total_cost": self.get_total_cost(),
            "by_model": self._stats.by_model,
            "first_request": self._stats.first_request,
            "last_request": self._stats.last_request,
        }
    
    def reset(self) -> None:
        """Reset all usage statistics."""
        self._stats = UsageStats()
        self._save()
    
    def format_stats(self) -> str:
        """Format stats for display."""
        stats = self.get_stats()
        
        if stats["total_requests"] == 0:
            return "📊 **Usage Statistics**\n\nNo usage recorded yet."
        
        lines = ["📊 **Usage Statistics**\n"]
        
        # Totals
        lines.append(f"**Total Requests:** {stats['total_requests']:,}")
        lines.append(f"**Total Tokens:** {stats['total_tokens']:,}")
        lines.append(f"  • Input: {stats['total_input_tokens']:,}")
        lines.append(f"  • Output: {stats['total_output_tokens']:,}")
        lines.append(f"**Estimated Cost:** ${stats['total_cost']:.4f}")
        
        # Per-model breakdown
        if stats["by_model"]:
            lines.append("\n**By Model:**")
            for model, model_stats in stats["by_model"].items():
                model_cost = self.get_cost(
                    model,
                    model_stats["input_tokens"],
                    model_stats["output_tokens"]
                )
                # Shorten model name for display
                short_name = model.split("-")[1] if "-" in model else model
                lines.append(
                    f"  • {short_name}: {model_stats['requests']} reqs, "
                    f"{model_stats['input_tokens'] + model_stats['output_tokens']:,} tokens, "
                    f"${model_cost:.4f}"
                )
        
        # Time range
        if stats["first_request"]:
            try:
                first = datetime.fromisoformat(stats["first_request"])
                last = datetime.fromisoformat(stats["last_request"])
                lines.append(f"\n**Period:** {first.strftime('%Y-%m-%d')} to {last.strftime('%Y-%m-%d')}")
            except Exception:
                pass
        
        return "\n".join(lines)
