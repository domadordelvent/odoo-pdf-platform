from io import BytesIO
from pypdf import PdfWriter

from pdf_engine.validator import validate_pdf


def rotate_pdf(pdf_file, angle):
    reader = validate_pdf(pdf_file)
    writer = PdfWriter()

    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()