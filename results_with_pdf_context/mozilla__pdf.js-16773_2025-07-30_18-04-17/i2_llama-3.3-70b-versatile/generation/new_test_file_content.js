#test/unit/stamp_spec.js
it("should only allow supported image types when selecting an image in the stamp annotation", async () => {
  const { StampEditor } = await import("./stamp.js");
  const { AnnotationEditorType } = await import("../../shared/util.js");
  const editor = new StampEditor({ type: AnnotationEditorType.STAMP });
  const input = document.createElement("input");
  input.type = "file";
  const originalAccept = StampEditor.supportedTypes;
  const unsupportedType = "image/tiff";
  const supportedType = "image/png";
  const file = new File([""], "test.png", { type: supportedType });
  const unsupportedFile = new File([""], "test.tiff", { type: unsupportedType });
  input.files = [unsupportedFile];
  const event = new Event("change");
  input.dispatchEvent(event);
  input.files = [file];
  const event2 = new Event("change");
  input.dispatchEvent(event2);
  expect(editor.#bitmap).not.toBeNull();
});