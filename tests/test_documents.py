"""Tests for document reading."""

import tempfile
from pathlib import Path

import pytest

from src.documents import DocumentReader


@pytest.fixture
def document_reader():
    """Create DocumentReader instance."""
    return DocumentReader()


def test_detect_type_txt(document_reader):
    """Test detecting TXT files."""
    doc_type = document_reader.detect_type("file.txt", "text/plain")
    assert doc_type == "txt"


def test_detect_type_pdf(document_reader):
    """Test detecting PDF files."""
    doc_type = document_reader.detect_type("file.pdf", "application/pdf")
    assert doc_type == "pdf"


def test_detect_type_docx(document_reader):
    """Test detecting DOCX files."""
    doc_type = document_reader.detect_type(
        "file.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert doc_type == "docx"


def test_detect_type_unsupported(document_reader):
    """Test unsupported file types return None."""
    doc_type = document_reader.detect_type("file.xyz", "application/unknown")
    assert doc_type is None


def test_detect_type_by_extension(document_reader):
    """Test detection by extension when mime is generic."""
    doc_type = document_reader.detect_type("file.pdf", "application/octet-stream")
    assert doc_type == "pdf"


def test_extract_txt(document_reader):
    """Test extracting text from TXT file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello, this is a test document.\nWith multiple lines.")
        f.flush()
        
        content = document_reader.extract_text(Path(f.name), "txt")
        
        assert "Hello" in content
        assert "multiple lines" in content


def test_extract_txt_encoding(document_reader):
    """Test TXT extraction handles encoding."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Unicode: café, naïve, 日本語")
        f.flush()
        
        content = document_reader.extract_text(Path(f.name), "txt")
        
        assert "café" in content
        assert "日本語" in content
