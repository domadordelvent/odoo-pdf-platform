/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PdfOperationSelector extends Component {
    static template = "document_pdf_tools.PdfOperationSelector";
    static props = {
        ...standardFieldProps,
    };

    get operations() {
        return [
            { value: "merge", label: "Merge", icon: "merge.png" },
            { value: "split", label: "Split", icon: "split.png" },
            { value: "rotate", label: "Rotate", icon: "rotate.png" },
            { value: "reorder", label: "Reorder", icon: "reorder.png" },
            { value: "extract", label: "Extract Pages", icon: "extract.png" },
            { value: "watermark", label: "Watermark", icon: "watermark.png" },
            { value: "compress", label: "Compress", icon: "compress.png" },
        ];
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    selectOperation(value) {
        if (this.props.readonly) {
            return;
        }

        this.props.record.update({
            [this.props.name]: value,
        });
    }

    iconUrl(icon) {
        return `/document_pdf_tools/static/src/img/operations/${icon}`;
    }
}

export const pdfOperationSelector = {
    component: PdfOperationSelector,
    supportedTypes: ["selection"],
};

registry.category("fields").add(
    "pdf_operation_selector",
    pdfOperationSelector
);
