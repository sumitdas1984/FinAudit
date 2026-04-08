"""Unit tests for PDF_Parser edge cases.

Requirements: 1.10, 1.12
"""
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.services.exceptions import NoExtractableTextError, PasswordProtectedError
from app.services.pdf_parser import PDF_Parser


@pytest.fixture
def parser():
    return PDF_Parser()


@pytest.fixture
def dummy_file():
    return BytesIO(b"%PDF-1.4 fake content")


def test_password_protected_pdf_raises_error(parser, dummy_file):
    """A PDF with encryption set should raise PasswordProtectedError. (Req 1.10)"""
    mock_pdf = MagicMock()
    mock_pdf.doc.encryption = {"Filter": "/Standard"}  # non-None signals encryption
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        with pytest.raises(PasswordProtectedError):
            parser.extract_text(dummy_file)


def test_image_only_pdf_raises_error(parser, dummy_file):
    """A PDF whose pages yield no text should raise NoExtractableTextError. (Req 1.12)"""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None  # image-only page returns None

    mock_pdf = MagicMock()
    mock_pdf.doc.encryption = None
    mock_pdf.pages = [mock_page, mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        with pytest.raises(NoExtractableTextError):
            parser.extract_text(dummy_file)


def test_image_only_pdf_whitespace_only_raises_error(parser, dummy_file):
    """Pages with only whitespace text are treated as image-only. (Req 1.12)"""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "   \n\t  "

    mock_pdf = MagicMock()
    mock_pdf.doc.encryption = None
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        with pytest.raises(NoExtractableTextError):
            parser.extract_text(dummy_file)
