class PdfEngineError(Exception):
    """Base exception for PDF processing errors."""


class PageSelectionError(ValueError):
    """Safe, user-facing page selection validation error."""
