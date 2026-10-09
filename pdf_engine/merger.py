from io import BytesIO
from itertools import islice

from pypdf import PdfWriter

from . import limits
from .validator import validate_pdf


def merge_pdfs(pdf_files):
    # Entries may be bytes or lazy byte loaders (used by Odoo). Bound even
    # generators before parsing PDFs; keep no collection of input readers.
    sources = list(islice(iter(pdf_files), limits.MAX_OPERATION_PDFS + 1))
    limits.check_pdf_count(len(sources))

    def load(source):
        return source() if callable(source) else source

    total = 0
    for source in sources:
        reader = validate_pdf(load(source))
        total += len(reader.pages)
        limits.check_total_pages(total)
        del reader

    # Preflight all inputs before allocating the output writer.
    writer = PdfWriter()
    total = 0
    for source in sources:
        reader = validate_pdf(load(source))
        total += len(reader.pages)
        limits.check_total_pages(total)
        for page in reader.pages:
            writer.add_page(page)
        del reader

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
