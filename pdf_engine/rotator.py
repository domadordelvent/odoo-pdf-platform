from io import BytesIO
from pypdf import PdfReader, PdfWriter


def rotate_pdf(pdf_file, angle):
    reader = PdfReader(BytesIO(pdf_file))
    writer = PdfWriter()

    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()