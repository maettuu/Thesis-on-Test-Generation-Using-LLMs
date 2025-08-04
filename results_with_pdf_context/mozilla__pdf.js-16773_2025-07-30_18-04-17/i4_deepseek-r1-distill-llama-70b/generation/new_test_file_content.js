#test/unit/stamp_spec.js
it("should only allow supported image types when selecting an image", async () => {
  const { StampEditor } = await import("../../display/editor/stamp.js");
  const { shadow } = await import("../../shared/util.js");

  const supportedTypes = [
    "image/apng",
    "image/avif",
    "image/bmp",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/svg+xml",
    "image/webp",
    "image/x-icon"
  ].join(",");

  const uiManager = {
    imageManager: {
      getFromId: () => null,
      getFromUrl: () => null,
      deleteId: () => null,
      isValidId: () => false
    }
  };

  const editor = new StampEditor({
    bitmapUrl: "test.jpg",
    parent: null,
    uiManager: uiManager,
    pageIndex: 0
  });

  const input = document.createElement("input");
  input.type = "file";

  const expectedAccept = supportedTypes;
  const actualAccept = input.accept;

  expect(actualAccept).toBe(expectedAccept);
});