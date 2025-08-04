#test/unit/to_unicode_map_spec.js
it("should render Extension B characters in form fields correctly", async () => {
  const { getDocument } = await import('../../display/api.js');
  const { buildGetDocumentParams } = await import('./test_utils.js');
  const loadingTask = getDocument(buildGetDocumentParams('issue19182.pdf'));
  const doc = await loadingTask.promise;
  const page = await doc.getPage(1);
  const textContent = await page.getTextContent();
  const expectedText = " Extension B character: ";
  const actualText = textContent.items[0].str;
  expect(actualText).toBe(expectedText);
});