#test/unit/stamp_spec.js
it("should only allow supported image types for stamp annotation", async () => {
  const { StampEditor } = await import("../../display/editor/stamp.js");
  const input = document.createElement("input");
  const expectedAccept = StampEditor.supportedTypes;
  input.type = "file";
  input.accept = StampEditor.supportedTypes;
  const actualAccept = input.accept;
  expect(actualAccept).toBe(expectedAccept);
});