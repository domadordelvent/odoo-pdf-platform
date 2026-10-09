import { beforeEach, expect, test } from "@odoo/hoot";
import { queryOne, setInputFiles } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    clickSave,
    contains,
    defineModels,
    fields,
    MockServer,
    mockService,
    models,
    mountView,
} from "@web/../tests/web_test_helpers";
import "@document_pdf_tools/fields/pdf_attachment_field";

class PdfJob extends models.Model {
    _name = "pdf.job";
    input_attachment_ids = fields.Many2many({ relation: "ir.attachment", string: "Input PDFs" });
    _records = [{ id: 1, input_attachment_ids: [1] }];
}

class IrAttachment extends models.Model {
    _name = "ir.attachment";
    name = fields.Char();
    mimetype = fields.Char();
    _records = [{ id: 1, name: "existing.pdf", mimetype: "application/pdf" }];
}

defineModels([PdfJob, IrAttachment]);

beforeEach(() => {
    mockService("http", {
        post(route, { ufile, model, id }) {
            expect(route).toBe("/web/binary/upload_attachment");
            expect(model).toBe("pdf.job");
            expect(id === 0 || id === 1).toBe(true);
            expect.step(ufile.map((file) => file.name).join(","));
            const ids = MockServer.env["ir.attachment"].create(
                ufile.map(({ name }) => ({ name, mimetype: "application/pdf" }))
            );
            return JSON.stringify(MockServer.env["ir.attachment"].read(ids));
        },
    });
});

const pdf = (name = "new.pdf", type = "application/pdf") =>
    new File(["%PDF-1.4\nfixture"], name, { type });

async function mountPdfField({ readonly = false, resId = 1 } = {}) {
    await mountView({
        type: "form",
        resModel: "pdf.job",
        resId,
        arch: `<form><field name="input_attachment_ids" widget="pdf_attachment" readonly="${readonly ? 1 : 0}"/></form>`,
    });
}

async function choose(files) {
    await contains(".o_attach").click();
    await setInputFiles(files);
    await animationFrame();
}

async function drop(files) {
    const dataTransfer = new DataTransfer();
    for (const file of files) {
        dataTransfer.items.add(file);
    }
    queryOne(".o_file_input").dispatchEvent(new DragEvent("dragenter", { bubbles: true, dataTransfer }));
    await animationFrame();
    expect(".o-Dropzone").toHaveCount(1);
    queryOne(".o-Dropzone").dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer }));
    await animationFrame();
}

test("choose multiple PDFs and preserve native cards, downloads, removal and saving", async () => {
    await mountPdfField();
    expect("input.o_input_file").toHaveAttribute("accept", ".pdf,application/pdf");
    expect("input.o_input_file").toHaveAttribute("multiple");
    await choose([pdf("first.pdf"), pdf("second.pdf")]);
    expect.verifySteps(["first.pdf,second.pdf"]);
    expect(".o_attachment").toHaveCount(3);
    expect(".o_attachment:nth-child(2) .caption:not(.small) a").toHaveText("first.pdf");
    expect(".o_attachment:first-child .caption:not(.small) a").toHaveAttribute("href", "/web/content/1?download=true");
    await contains(".o_attachment:first-child .o_attachment_delete").click();
    await clickSave();
    expect(".o_attachment").toHaveCount(2);
    expect(MockServer.env["pdf.job"].read(1)[0].input_attachment_ids).toHaveLength(2);
});

test("drop multiple PDFs through the native upload and attachment mechanism", async () => {
    await mountPdfField();
    await drop([pdf("first.pdf"), pdf("second.PDF", "")]);
    expect.verifySteps(["first.pdf,second.PDF"]);
    expect(".o_attachment").toHaveCount(3);
    expect(".o_attachment:nth-child(3) .caption:not(.small) a").toHaveText("second.PDF");
});

for (const [method, upload] of [["choose", choose], ["drop", drop]]) {
    test(`${method}: reject a mixed selection without uploading any files`, async () => {
        await mountPdfField();
        await upload([pdf(), new File(["text"], "notes.txt", { type: "text/plain" })]);
        expect.verifySteps([]);
        expect(".o_notification_content").toHaveText(
            "Only PDF files are supported. No files were uploaded. Unsupported files: notes.txt"
        );
        expect(".o_attachment").toHaveCount(1);
        expect("input.o_input_file").toBeEnabled();
        await upload([pdf("retry.pdf")]);
        expect.verifySteps(["retry.pdf"]);
        expect(".o_attachment").toHaveCount(2);
    });
}

test("reject a non-PDF renamed to .pdf", async () => {
    await mountPdfField();
    await choose([new File(["not a PDF"], "renamed.pdf", { type: "application/pdf" })]);
    expect.verifySteps([]);
    expect(".o_notification_content").toHaveText(
        "Only PDF files are supported. No files were uploaded. Unsupported files: renamed.pdf"
    );
    expect(".o_attachment").toHaveCount(1);
});

test("drop PDFs on an unsaved job and save the attachment relation", async () => {
    await mountPdfField({ resId: false });
    await drop([pdf()]);
    expect.verifySteps(["new.pdf"]);
    await clickSave();
    expect(".o_attachment").toHaveCount(1);
    expect(MockServer.env["pdf.job"].search_read([["id", "!=", 1]])[0].input_attachment_ids).toHaveLength(1);
});

test("readonly attachments retain downloads but expose no upload or removal controls", async () => {
    await mountPdfField({ readonly: true });
    expect(".o_attachment").toHaveCount(1);
    expect(".o_attach").toHaveCount(0);
    expect(".o_attachment_delete").toHaveCount(0);
    expect(".o_file_input").toHaveCount(0);
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(pdf());
    queryOne(".o_attachment").dispatchEvent(new DragEvent("dragenter", { bubbles: true, dataTransfer }));
    await animationFrame();
    expect(".o-Dropzone").toHaveCount(0);
    expect.verifySteps([]);
});
