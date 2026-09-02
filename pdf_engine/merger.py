from io import BytesIO
from pypdf import PdfReader, PdfWriter


def merge_pdfs(pdf_files):
    writer = PdfWriter()

    for pdf_file in pdf_files:
        reader = PdfReader(BytesIO(pdf_file))

        for page in reader.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()
