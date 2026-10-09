import { useRef } from "@odoo/owl";
import { useDropzone } from "@web/core/dropzone/dropzone_hook";
import { FileInput } from "@web/core/file_input/file_input";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    Many2ManyBinaryField,
    many2ManyBinaryField,
} from "@web/views/fields/many2many_binary/many2many_binary_field";

class PdfFileInput extends FileInput {
    static template = "document_pdf_tools.PdfFileInput";

    setup() {
        super.setup();
        this.notification = useService("notification");
        const dropzone = useRef("pdf-dropzone");
        useDropzone(dropzone, (event) => this.onDrop(event), "", () => !this.state.isDisable);
    }

    async onDrop(event) {
        event.preventDefault();
        if (this.state.isDisable || !event.dataTransfer?.files.length) {
            return;
        }
        this.fileInputRef.el.files = event.dataTransfer.files;
        await this.onFileInputChange();
    }

    async onFileInputChange() {
        if (this.state.isDisable) {
            return;
        }
        this.state.isDisable = true;
        try {
            const files = [...this.fileInputRef.el.files];
            if (!files.length) {
                return;
            }
            const unsupported = [];
            for (const file of files) {
                // Check the header as well as the name; browsers may omit MIME types.
                const header = await file.slice(0, 1024).text();
                if (!/\.pdf$/i.test(file.name) || !header.includes("%PDF-")) {
                    unsupported.push(file.name);
                }
            }
            if (unsupported.length) {
                this.notification.add(
                    _t("Only PDF files are supported. No files were uploaded. Unsupported files: %s", unsupported.join(", ")),
                    { title: _t("PDF upload"), type: "danger" }
                );
                return;
            }
            await super.onFileInputChange();
        } finally {
            this.fileInputRef.el.value = "";
            this.state.isDisable = false;
        }
    }
}

export class PdfAttachmentField extends Many2ManyBinaryField {
    static template = "document_pdf_tools.PdfAttachmentField";
    static components = { ...Many2ManyBinaryField.components, FileInput: PdfFileInput };
}

registry.category("fields").add("pdf_attachment", {
    ...many2ManyBinaryField,
    component: PdfAttachmentField,
});
