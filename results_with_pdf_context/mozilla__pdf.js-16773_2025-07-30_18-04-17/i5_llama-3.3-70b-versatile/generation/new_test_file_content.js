#test/unit/stamp_spec.js
it("should only allow supported image types when selecting an image in the stamp annotation", async () => {
  const { AnnotationEditorType, shadow } = await import("../../shared/util.js");
  const { StampEditor } = await import("./stamp.js");

  const supportedTypes = await StampEditor.supportedTypes;
  const unsupportedType = "image/tiff";

  expect(supportedTypes).not.toContain(unsupportedType);
  const input = document.createElement("input");
  input.type = "file";
  input.accept = supportedTypes;
  document.body.appendChild(input);

  const changeEvent = new Event("change");
  input.dispatchEvent(changeEvent);

  const file = new File([""], "example.tiff", { type: "image/tiff" });
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  input.files = dataTransfer.files;

  const editor = new StampEditor();
  await editor.load(input);

  expect(editor.#bitmapPromise).toBeNull();
});