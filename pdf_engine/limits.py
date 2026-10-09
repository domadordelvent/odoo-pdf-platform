"""Resource policy shared by Odoo and the standalone engine (MiB for bytes)."""
from .exceptions import PdfEngineError

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 300
MAX_OPERATION_PDFS = 10
MAX_OPERATION_PAGES = 1000


def check_pdf_size(size):
    if size > MAX_PDF_BYTES:
        raise PdfEngineError(f"Each PDF must be at most {MAX_PDF_BYTES / (1024 * 1024):g} MB.")


def check_pdf_count(count):
    if count > MAX_OPERATION_PDFS:
        raise PdfEngineError(f"An operation accepts at most {MAX_OPERATION_PDFS} PDFs.")


def check_page_count(count):
    if count > MAX_PDF_PAGES:
        raise PdfEngineError(f"Each PDF must contain at most {MAX_PDF_PAGES} pages.")


def check_total_pages(count):
    if count > MAX_OPERATION_PAGES:
        raise PdfEngineError(f"An operation accepts at most {MAX_OPERATION_PAGES} pages in total.")
