#test/unit/stamp_spec.js
import { AnnotationEditorType } from "../../shared/util.js";
import { StampEditor } from "./stamp.js";

describe("Stamp Editor Image Type Validation", () => {
  it("should only allow supported image types when selecting an image in the stamp annotation", async () => {
    const supportedTypes = StampEditor.supportedTypes;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = supportedTypes;

    const file = new File([""], "test.tiff", { type: "image/tiff" });
    const file2 = new File([""], "test.png", { type: "image/png" });

    const changeEvent = new Event("change");
    input.files = [file];
    input.dispatchEvent(changeEvent);

    const changeEvent2 = new Event("change");
    input.files = [file2];
    input.dispatchEvent(changeEvent2);

    const supported = supportedTypes.includes(file2.type);
    const unsupported = supportedTypes.includes(file.type);

    expect(supported).toBe(true);
    expect(unsupported).toBe(false);
  });
});