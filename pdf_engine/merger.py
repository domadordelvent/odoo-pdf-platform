from io import BytesIO
from pypdf import PdfWriter

from pdf_engine.validator import validate_pdf


def merge_pdfs(pdf_files):
    writer = PdfWriter()

    for pdf_file in pdf_files:
        reader = validate_pdf(pdf_file)

        for page in reader.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()
