#test/unit/to_unicode_map_spec.js
it("should render Extension B characters in form fields correctly", async () => {
  const { PDFDocument } = await import("../../core/document.js");
  const { PDFFetchStream } = await import("../../display/fetch_stream.js");
  const pdf = await PDFDocument.load(await PDFFetchStream.fetch("https://github.com/user-attachments/files/18037940/ExtnB.character.not.working.pdf"));
  const page = await pdf.getPage(1);
  const textContent = await page.getTextContent();
  const expectedText = "Extension B character: ";
  const actualText = textContent.items[0].str;
  expect(actualText).toContain(expectedText);
});