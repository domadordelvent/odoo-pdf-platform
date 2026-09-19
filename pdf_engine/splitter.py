from io import BytesIO
from pypdf import PdfWriter

from pdf_engine.validator import validate_pdf


def split_pdf(pdf_file):
    reader = validate_pdf(pdf_file)
    outputs = []

    for index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)

        output = BytesIO()
        writer.write(output)

        outputs.append(
            {
                "page": index,
                "data": output.getvalue(),
            }
        )

    return outputs