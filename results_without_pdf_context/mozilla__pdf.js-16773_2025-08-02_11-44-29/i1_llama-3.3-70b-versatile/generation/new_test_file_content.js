#test/unit/stamp_spec.js
import { AnnotationEditorType } from "../../shared/util.js";
import { StampEditor } from "./stamp.js";

describe("Stamp Editor", () => {
  it("only allows supported image types when selecting an image", async () => {
    const stampEditor = new StampEditor({});

    const input = document.createElement("input");
    input.type = "file";
    stampEditor._uiManager = {
      imageManager: {
        getFromFile: (file) => {
          return new Promise((resolve) => {
            resolve({
              bitmap: "bitmap",
              id: "id",
              isSvg: false,
            });
          });
        },
      },
    };

    const file = new File([""], "test.tiff", { type: "image/tiff" });
    const files = [file];
    const changeEvent = new Event("change");
    Object.defineProperty(input, "files", { value: files });
    input.dispatchEvent(changeEvent);

    const supportedTypes = StampEditor.supportedTypes;
    const isSupported = supportedTypes.includes("image/tiff");

    expect(isSupported).toBe(false);
  });
});