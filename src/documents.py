"""
Document reading for MayaLite v0.4.

Handles document attachments (PDF, TXT, DOCX).
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class DocumentReader:
    """
    Reads and extracts text from documents.
    
    Supports: PDF, TXT, DOCX
    """
    
    # Supported document types
    SUPPORTED_TYPES = {
        "application/pdf": "pdf",
        "text/plain": "txt",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    }
    
    # Max document size (10MB)
    MAX_SIZE = 10 * 1024 * 1024
    
    # Max text length for Claude
    MAX_TEXT_LENGTH = 100000
    
    def __init__(self):
        pass
    
    async def download_telegram_document(
        self,
        bot,
        document,
    ) -> Tuple[bytes, str, str]:
        """
        Download a document from Telegram.
        
        Args:
            bot: Telegram bot instance
            document: Telegram Document object
            
        Returns:
            Tuple of (file_bytes, mime_type, filename)
        """
        file = await bot.get_file(document.file_id)
        
        mime_type = document.mime_type or "application/octet-stream"
        filename = document.file_name or "document"
        
        # Download to temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = Path(tmp.name)
        
        try:
            file_bytes = tmp_path.read_bytes()
            
            if len(file_bytes) > self.MAX_SIZE:
                raise ValueError(f"Document too large: {len(file_bytes)} bytes (max {self.MAX_SIZE})")
            
            return file_bytes, mime_type, filename
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
    
    def detect_type(self, filename: str, mime_type: str) -> Optional[str]:
        """
        Detect document type from filename and mime type.
        
        Returns: "pdf", "txt", "docx", or None
        """
        # Check mime type first
        if mime_type in self.SUPPORTED_TYPES:
            return self.SUPPORTED_TYPES[mime_type]
        
        # Fall back to extension
        ext = Path(filename).suffix.lower()
        
        if ext == ".pdf":
            return "pdf"
        elif ext in (".txt", ".text", ".md", ".markdown"):
            return "txt"
        elif ext == ".docx":
            return "docx"
        
        return None
    
    def extract_text(
        self,
        file_bytes: bytes,
        doc_type: str,
    ) -> str:
        """
        Extract text from document bytes.
        
        Args:
            file_bytes: Raw document bytes
            doc_type: Document type ("pdf", "txt", "docx")
            
        Returns:
            Extracted text
        """
        if doc_type == "txt":
            return self._extract_txt(file_bytes)
        elif doc_type == "pdf":
            return self._extract_pdf(file_bytes)
        elif doc_type == "docx":
            return self._extract_docx(file_bytes)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")
    
    def _extract_txt(self, file_bytes: bytes) -> str:
        """Extract text from plain text file."""
        # Try common encodings
        for encoding in ["utf-8", "latin-1", "cp1252"]:
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        # Last resort: ignore errors
        return file_bytes.decode("utf-8", errors="ignore")
    
    def _extract_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF."""
        try:
            from pypdf import PdfReader
            import io
            
            reader = PdfReader(io.BytesIO(file_bytes))
            
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
            
        except ImportError:
            raise ImportError("pypdf not installed. Run: pip install pypdf")
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            raise
    
    def _extract_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX."""
        try:
            from docx import Document
            import io
            
            doc = Document(io.BytesIO(file_bytes))
            
            text_parts = []
            for para in doc.paragraphs:
                if para.text:
                    text_parts.append(para.text)
            
            return "\n\n".join(text_parts)
            
        except ImportError:
            raise ImportError("python-docx not installed. Run: pip install python-docx")
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            raise
    
    def truncate_text(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Truncate text to max length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length (default: MAX_TEXT_LENGTH)
            
        Returns:
            Truncated text with note if truncated
        """
        max_len = max_length or self.MAX_TEXT_LENGTH
        
        if len(text) <= max_len:
            return text
        
        truncated = text[:max_len]
        return truncated + "\n\n[... document truncated ...]"
    
    async def read_and_extract(
        self,
        bot,
        document,
    ) -> Tuple[str, str]:
        """
        Download and extract text from a Telegram document.
        
        Args:
            bot: Telegram bot instance
            document: Telegram Document object
            
        Returns:
            Tuple of (extracted_text, filename)
        """
        file_bytes, mime_type, filename = await self.download_telegram_document(
            bot, document
        )
        
        doc_type = self.detect_type(filename, mime_type)
        
        if not doc_type:
            raise ValueError(
                f"Unsupported document type: {filename} ({mime_type}). "
                "Supported: PDF, TXT, DOCX"
            )
        
        text = self.extract_text(file_bytes, doc_type)
        text = self.truncate_text(text)
        
        return text, filename
