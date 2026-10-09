"""In-memory PDF fixtures shared by engine tests."""

from io import BytesIO

from pypdf import PdfWriter


def make_pdf(widths=(72,), password=None):
    """Build a PDF; empty widths give zero pages, None disables encryption."""
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=300)
    if password is not None:
        writer.encrypt(password)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
