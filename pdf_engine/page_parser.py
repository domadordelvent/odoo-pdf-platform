import re

from .exceptions import PageSelectionError
from . import limits


def parse_page_selection(selection, total_pages):
    """Validate the whole selection against the PDF before expanding any range."""
    if not isinstance(selection, str):
        raise PageSelectionError("Invalid page selection.")

    def validated_ranges():
        for part in selection.split(","):
            match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?", part)
            if not match:
                raise PageSelectionError("Invalid page selection.")
            start = int(match[1])
            end = int(match[2]) if match[2] is not None else start
            if start > end:
                raise PageSelectionError("Page ranges must be ascending.")
            if start < 1 or start > total_pages:
                raise PageSelectionError(f"Page {start} does not exist.")
            if end > total_pages:
                raise PageSelectionError(f"Page {end} does not exist.")
            yield start, end

    # Two passes avoid expanding even an earlier valid range when a later
    # component is invalid, without storing an intermediate list of ranges.
    selected_count = 0
    for start, end in validated_ranges():
        selected_count += end - start + 1
        limits.check_total_pages(selected_count)

    pages = []
    for start, end in validated_ranges():
        pages.extend(range(start, end + 1))
    return pages
