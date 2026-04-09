from typing import BinaryIO

import pdfplumber

from app.services.exceptions import NoExtractableTextError, ParseError, PasswordProtectedError


class PDF_Parser:
    def extract_text(self, file: BinaryIO) -> str:
        """Extract text from a PDF file-like object.

        Returns all page text joined by newlines.

        Raises:
            PasswordProtectedError: If the PDF is encrypted/password-protected.
            NoExtractableTextError: If all pages yield empty text (image-only PDF).
            ParseError: For any other parsing failure.
        """
        try:
            with pdfplumber.open(file) as pdf:
                if pdf.doc.encryption is not None:
                    raise PasswordProtectedError("PDF is password-protected")

                pages_text = [page.extract_text() or "" for page in pdf.pages]

        except PasswordProtectedError:
            raise
        except Exception as exc:
            raise ParseError(f"Failed to parse PDF: {exc}") from exc

        if not any(text.strip() for text in pages_text):
            raise NoExtractableTextError("PDF contains no extractable text (image-only)")

        return "\n".join(pages_text)
