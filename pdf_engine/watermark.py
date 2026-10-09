from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from pdf_engine.validator import validate_pdf


def _create_watermark(width, height, text):
    buffer = BytesIO()

    pdf = canvas.Canvas(buffer, pagesize=(width, height))

    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 50)
    pdf.setFillAlpha(0.20)

    pdf.translate(width / 2, height / 2)
    pdf.rotate(45)

    pdf.drawCentredString(0, 0, text)

    pdf.restoreState()
    pdf.save()

    buffer.seek(0)

    return PdfReader(buffer).pages[0]


def add_watermark(pdf_file, text):
    reader = validate_pdf(pdf_file)
    writer = PdfWriter()

    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        watermark = _create_watermark(width, height, text)

        page.merge_page(watermark)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()