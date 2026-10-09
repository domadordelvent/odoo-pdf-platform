{
    "name": "Document PDF Tools",
    "version": "18.0.1.0.0",
    "summary": "PDF processing platform integrated with Odoo",
    "category": "Productivity/Documents",
    "author": "Jordi",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "security/pdf_job_rules.xml",
        "views/pdf_job_list_views.xml",
        "views/pdf_job_kanban_views.xml",
        "views/pdf_job_form_views.xml",
        "views/pdf_job_menu.xml",   
    ],
    "assets": {
        "web.assets_backend": [
            "document_pdf_tools/static/src/fields/pdf_attachment_field.js",
            "document_pdf_tools/static/src/fields/pdf_attachment_field.xml",
            "document_pdf_tools/static/src/fields/pdf_operation_selector.js",
            "document_pdf_tools/static/src/fields/pdf_operation_selector.xml",
        ],
        "web.assets_unit_tests": [
            "document_pdf_tools/static/tests/pdf_attachment_field.test.js",
        ],
    },
    "application": True,
    "installable": True,
}
