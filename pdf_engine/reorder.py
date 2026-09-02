from io import BytesIO

from pypdf import PdfReader, PdfWriter

from .page_parser import parse_page_selection


def reorder_pages(pdf_file, order):
    reader = PdfReader(BytesIO(pdf_file))
    writer = PdfWriter()

    pages = parse_page_selection(order)
    total_pages = len(reader.pages)

    expected_pages = list(range(1, total_pages + 1))

    if sorted(pages) != expected_pages:
        raise ValueError(
            f"Reorder requires all pages exactly once. "
            f"Expected pages: 1-{total_pages}"
        )

    for page_number in pages:
        writer.add_page(reader.pages[page_number - 1])

    output = BytesIO()
    writer.write(output)

    return output.getvalue()