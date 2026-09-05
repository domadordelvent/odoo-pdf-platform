import subprocess
import tempfile
from pathlib import Path

from .exceptions import PdfEngineError


COMPRESSION_PROFILES = {
    "low": "/printer",
    "medium": "/ebook",
    "high": "/screen",
}


def compress_pdf(pdf_bytes, level):
    profile = COMPRESSION_PROFILES.get(level)
    if not profile:
        raise PdfEngineError(f"Unsupported compression level: {level}")

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
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
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

        if not output_path.is_file():
            raise PdfEngineError(
                "Ghostscript compression failed: no output PDF was created."
            )

        return output_path.read_bytes()
