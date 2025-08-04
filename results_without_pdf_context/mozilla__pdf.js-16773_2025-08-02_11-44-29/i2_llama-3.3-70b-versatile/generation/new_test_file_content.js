#test/unit/stamp_spec.js
it("should only allow supported image types when selecting an image in the stamp annotation", async () => {
  const { StampEditor } = await import("./stamp.js");
  const { AnnotationEditorType } = await import("../../shared/util.js");
  const input = document.createElement("input");
  input.type = "file";
  const stampEditor = new StampEditor({ type: AnnotationEditorType.STAMP });
  stampEditor._uiManager = { imageManager: { getFromFile: () => Promise.resolve({ bitmap: "image", id: 1, isSvg: false }) } };
  stampEditor.#getBitmap();
  input.accept = "image/tiff";
  const event = new Event("change");
  event.target = { files: [new File(["image"], "image.tiff", { type: "image/tiff" })] };
  await new Promise(resolve => {
    input.addEventListener("change", () => {
      resolve();
    });
    input.dispatchEvent(event);
  });
  expect(stampEditor.#bitmap).toBeNull();
});