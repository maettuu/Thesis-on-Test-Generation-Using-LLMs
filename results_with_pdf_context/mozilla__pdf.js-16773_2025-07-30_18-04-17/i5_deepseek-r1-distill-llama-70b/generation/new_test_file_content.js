#test/unit/stamp_spec.js
it("should only accept supported image types when selecting an image", async () => {
  const { StampEditor } = await import("../../display/editor/stamp.js");
  const editor = new StampEditor();

  const input = editor._uiManager._input;
  const expectedTypes = StampEditor.supportedTypes;

  expect(input.accept).toBe(expectedTypes);
});