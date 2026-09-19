from io import BytesIO

from pypdf import PdfWriter

from pdf_engine.validator import validate_pdf

from .page_parser import parse_page_selection


def extract_pages(pdf_file, selection):
    reader = validate_pdf(pdf_file)
    writer = PdfWriter()

    pages = parse_page_selection(selection)

    for page_number in pages:
        index = page_number - 1

        if index < 0 or index >= len(reader.pages):
            raise ValueError(f"Page {page_number} does not exist.")

        writer.add_page(reader.pages[index])

    output = BytesIO()
    writer.write(output)

    return output.getvalue()