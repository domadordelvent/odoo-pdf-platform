# Resource limits (V3)

The policy lives in `pdf_engine/limits.py` and is shared by the standalone
engine and `addons/document_pdf_tools`:

- Input PDF size: 25 MiB (26,214,400 bytes), inclusive.
- Input PDF pages: 300, inclusive.
- Input PDFs per operation: 10, inclusive.
- Input pages per operation: 1,000, inclusive.
- Expanded page selections: 1,000 entries, including repeated pages.

All seven operations use the shared validator. Odoo checks attachment count
and size metadata before reading binary data, checks actual bytes again,
and disables binary prefetch and releases the binary cache after loading.
Merge uses lazy attachment loaders and a sequential preflight before creating
its writer; inputs are read again during processing so input readers are not
retained together. The engine also bounds iterable input counts before parsing.

The declared PDF page count is checked before flattening the page tree, and
actual pages are checked too; a forged low count cannot bypass validation.
V1 access checks and V2 range validation remain in place. Unexpected errors
are logged server-side and shown to the user as a generic failure. Ghostscript
errors do not return raw diagnostics. Compression checks output file size
before reading it and retains TemporaryDirectory cleanup on failure.

These are admission limits, not hard CPU or memory limits. A PDF under these
limits can still have expensive compressed streams, images, nested objects,
or a dishonest page tree. pypdf may flatten that tree internally before yielding
pages. Processing and generated results still occupy memory. Merge outputs
may have up to 1,000 pages; the 300-page limit applies to each input PDF.
Output sizes (except compression), decoded stream sizes, concurrent jobs,
upload/storage quotas and request rates are not capped here. Only Ghostscript
has the existing 60-second timeout; other operations have no engine deadline.
Hard worker isolation and memory/CPU enforcement require separate deployment
work and are outside this change. Docker configuration was not changed.
