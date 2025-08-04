#test/unit/stamp_spec.js
import { AnnotationEditorType, shadow } from "../../shared/util.js";
import { StampEditor } from "../../display/editor/stamp.js";

describe("StampEditor", () => {
  it("should only accept supported image types", async () => {
    const editor = new StampEditor({ bitmapUrl: "" });
    const supportedTypes = StampEditor.supportedTypes.split(",").map(type => type.trim());

    const expectedTypes = [
      "image/apng",
      "image/avif",
      "image/bmp",
      "image/gif",
      "image/jpeg",
      "image/png",
      "image/svg+xml",
      "image/webp",
      "image/x-icon"
    ];

    expectedTypes.forEach(type => {
      expect(supportedTypes).toContain(type);
    });
  });
});