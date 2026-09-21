import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter

from .exceptions import PdfEngineError
from pdf_engine.validator import validate_pdf


GHOSTSCRIPT_TIMEOUT_SECONDS = 60


COMPRESSION_PROFILES = {
    "low": "/printer",
    "medium": "/ebook",
    "high": "/screen",
}


def compress_pdf(pdf_bytes, level):
    profile = COMPRESSION_PROFILES.get(level)
    if not profile:
        raise PdfEngineError(f"Unsupported compression level: {level}")

    reader = validate_pdf(pdf_bytes)
    if reader.is_encrypted:
        # Validation unlocked the reader; serialize without encryption for gs.
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        decrypted = BytesIO()
        writer.write(decrypted)
        pdf_bytes = decrypted.getvalue()

    with tempfile.TemporaryDirectory() as temporary_directory:
        input_path = Path(temporary_directory) / "input.pdf"
        output_path = Path(temporary_directory) / "output.pdf"
        input_path.write_bytes(pdf_bytes)

        command = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS={profile}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            str(input_path),
        ]

        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=GHOSTSCRIPT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            raise PdfEngineError(
                f"Ghostscript compression timed out after {GHOSTSCRIPT_TIMEOUT_SECONDS} seconds."
            ) from error
        except FileNotFoundError as error:
            raise PdfEngineError(
                "Ghostscript executable was not found."
            ) from error
        except subprocess.CalledProcessError as error:
            details = (
                error.stderr.strip()
                or error.stdout.strip()
                or "Unknown Ghostscript error."
            )
            raise PdfEngineError(
                f"Ghostscript compression failed: {details}"
            ) from error

        # Ghostscript can report a failed page while exiting successfully.
        diagnostics = "\n".join((result.stdout, result.stderr)).strip()
        if "page drawing error" in diagnostics.casefold():
            raise PdfEngineError(
                f"Ghostscript compression failed: {diagnostics}"
            )

        if not output_path.is_file():
            raise PdfEngineError(
                "Ghostscript compression failed: no output PDF was created."
            )

        compressed_pdf = output_path.read_bytes()
        validate_pdf(compressed_pdf)
        return compressed_pdf
