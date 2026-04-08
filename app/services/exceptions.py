class PasswordProtectedError(Exception):
    """Raised when a PDF is encrypted or password-protected."""


class NoExtractableTextError(Exception):
    """Raised when a PDF contains no extractable text (image-only)."""


class ParseError(Exception):
    """Raised for general PDF parsing failures."""


class UnrecognizedHeaderError(Exception):
    """Raised when no registered adapter matches the CSV headers."""


class UnrecognizedBankFormatError(Exception):
    """Raised when no registered adapter matches the PDF text."""
