import unittest
from unittest.mock import patch

from pdf_engine.page_parser import parse_page_selection
from pdf_engine.extractor import extract_pages
from pdf_engine.reorder import reorder_pages
from tests.pdf_helpers import make_pdf


class PageSelectionTests(unittest.TestCase):
    def test_invalid_selection_is_rejected_before_any_expansion(self):
        selections = (
            "1-1000000000", "1-4", "4-5", "4", "3-1", "0", "0-2",
            "", "abc", "1,", ",1", "1-", "1-2-3", "-1", "1.5",
            "1--2", "1,3-1", "1-3,1-1000000000", "1-3,abc",
            None, 1, "9" * 5000,
        )
        for selection in selections:
            with self.subTest(selection=selection):
                with patch("pdf_engine.page_parser.range", create=True) as expand:
                    with self.assertRaises(ValueError):
                        parse_page_selection(selection, 3)
                    expand.assert_not_called()

    def test_valid_selection_preserves_order_and_duplicates(self):
        self.assertEqual(parse_page_selection(" 3, 1 - 2, 2 ", 3), [3, 1, 2, 2])
        self.assertEqual(parse_page_selection("1-3", 3), [1, 2, 3])
        self.assertEqual(parse_page_selection("1", 1), [1])

    def test_processors_reject_invalid_ranges(self):
        source = make_pdf([72, 144, 216])
        for processor in (extract_pages, reorder_pages):
            for selection in ("1-1000000000", "1-4", "4", "0,1,2", "3-1", "3-1,1-3", "1,,2", "1-2-3"):
                with self.subTest(processor=processor.__name__, selection=selection):
                    with self.assertRaises(ValueError):
                        processor(source, selection)
