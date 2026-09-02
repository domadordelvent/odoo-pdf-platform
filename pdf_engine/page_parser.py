def parse_page_selection(selection):
    pages = []

    for part in selection.split(","):
        part = part.strip()

        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))

    return pages