#test/unit/stamp_spec.js
import { StampEditor } from "../../display/editor/stamp.js";
import { AnnotationEditorType } from "../../shared/util.js";

describe("StampEditor", () => {
  it("should only accept supported image types", async () => {
    const editor = new StampEditor({} as unknown as AnnotationEditorType);
    const expectedTypes = [
      "image/apng",
      "image/avif",
      "image/bmp",
      "image/gif",
      "image/jpeg",
      "image/png",
      "image/svg+xml",
      "image/webp",
      "image/x-icon",
    ].join(",");

    expect(editor.constructor.supportedTypes).toBe(expectedTypes);
  });
});