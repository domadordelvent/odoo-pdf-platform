from io import BytesIO
from pypdf import PdfReader, PdfWriter


def split_pdf(pdf_file):
    reader = PdfReader(BytesIO(pdf_file))
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