"""
Image understanding for MayaLite v0.4.

Handles photo messages via Claude's vision capability.
"""

import base64
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class VisionHandler:
    """
    Handles image understanding using Claude's vision capability.
    """
    
    # Supported image types
    SUPPORTED_TYPES = {
        "image/jpeg": "jpeg",
        "image/png": "png", 
        "image/gif": "gif",
        "image/webp": "webp",
    }
    
    # Max image size (20MB as per Claude limits)
    MAX_SIZE = 20 * 1024 * 1024
    
    def __init__(self):
        pass
    
    async def download_telegram_photo(
        self,
        bot,
        photo_file_id: str
    ) -> tuple[bytes, str]:
        """
        Download a photo from Telegram.
        
        Args:
            bot: Telegram bot instance
            photo_file_id: Telegram file ID for the photo
            
        Returns:
            Tuple of (image_bytes, mime_type)
        """
        file = await bot.get_file(photo_file_id)
        
        # Determine mime type from file path
        file_path = file.file_path or ""
        if file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif file_path.endswith(".png"):
            mime_type = "image/png"
        elif file_path.endswith(".gif"):
            mime_type = "image/gif"
        elif file_path.endswith(".webp"):
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"  # Default
        
        # Download to temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = Path(tmp.name)
        
        try:
            image_bytes = tmp_path.read_bytes()
            
            if len(image_bytes) > self.MAX_SIZE:
                raise ValueError(f"Image too large: {len(image_bytes)} bytes (max {self.MAX_SIZE})")
            
            return image_bytes, mime_type
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
    
    def encode_image(self, image_bytes: bytes) -> str:
        """
        Encode image bytes to base64.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Base64 encoded string
        """
        return base64.standard_b64encode(image_bytes).decode("utf-8")
    
    def build_image_content(
        self,
        image_bytes: bytes,
        mime_type: str,
        caption: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Build Claude message content with image.
        
        Args:
            image_bytes: Raw image bytes
            mime_type: MIME type of the image
            caption: Optional text caption
            
        Returns:
            List of content blocks for Claude API
        """
        if mime_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported image type: {mime_type}")
        
        content = []
        
        # Add image block
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": self.encode_image(image_bytes),
            }
        })
        
        # Add text block if caption provided
        if caption:
            content.append({
                "type": "text",
                "text": caption
            })
        else:
            content.append({
                "type": "text",
                "text": "What's in this image?"
            })
        
        return content
    
    def get_best_photo_size(self, photo_sizes: list) -> Any:
        """
        Get the best (largest) photo size from Telegram's photo sizes.
        
        Args:
            photo_sizes: List of PhotoSize objects from Telegram
            
        Returns:
            Best PhotoSize object
        """
        if not photo_sizes:
            raise ValueError("No photo sizes available")
        
        # Sort by file_size (or width*height if file_size not available)
        return max(
            photo_sizes,
            key=lambda p: p.file_size if p.file_size else (p.width * p.height)
        )
