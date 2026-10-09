from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PyPdfError

from pdf_engine.exceptions import PdfEngineError
from . import limits


def validate_pdf(pdf_bytes):
    """Return a readable PDF reader after loading its page structure.

    Encrypted PDFs must open with an empty password. This does not validate
    every page content stream or reject damage that pypdf can recover from.
    """
    limits.check_pdf_count(1)
    limits.check_pdf_size(len(pdf_bytes))
    if not pdf_bytes:
        raise PdfEngineError("The PDF is empty.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.is_encrypted and not reader.decrypt(""):
            raise PdfEngineError("The PDF is encrypted and requires a password.")

        # Reject an oversized declared page tree before pypdf flattens it.
        # A low or missing /Count is not trusted: actual pages are checked below.
        declared_count = reader.trailer["/Root"]["/Pages"].get("/Count")
        if isinstance(declared_count, int):
            limits.check_page_count(declared_count)
            limits.check_total_pages(declared_count)

        # Iterate: an encrypted PDF's page count alone may not load the page tree.
        count = 0
        for page in reader.pages:
            count += 1
            limits.check_page_count(count)
            limits.check_total_pages(count)
        if not count:
            raise PdfEngineError("The PDF has no pages.")
    except (FileNotDecryptedError, DependencyError) as error:
        raise PdfEngineError("The encrypted PDF could not be processed.") from error
    except (PyPdfError, ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
        raise PdfEngineError("The PDF is unreadable or corrupt.") from error

    return reader
