from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PyPdfError

from pdf_engine.exceptions import PdfEngineError


def validate_pdf(pdf_bytes):
    """Return a readable PDF reader after loading its page structure.

    Encrypted PDFs must open with an empty password. This does not validate
    every page content stream or reject damage that pypdf can recover from.
    """
    if not pdf_bytes:
        raise PdfEngineError("The PDF is empty.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.is_encrypted and not reader.decrypt(""):
            raise PdfEngineError("The PDF is encrypted and requires a password.")

        # Iterate: an encrypted PDF's page count alone may not load the page tree.
        pages = list(reader.pages)
        if not pages:
            raise PdfEngineError("The PDF has no pages.")
    except (FileNotDecryptedError, DependencyError) as error:
        raise PdfEngineError("The encrypted PDF could not be processed.") from error
    except (PyPdfError, ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
        raise PdfEngineError("The PDF is unreadable or corrupt.") from error

    return reader
