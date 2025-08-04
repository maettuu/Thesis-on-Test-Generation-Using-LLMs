#test/unit/to_unicode_map_spec.js
it("should correctly map Extension B characters using codePointAt", async () => {
  const { ToUnicodeMap } = await import("../../core/to_unicode_map.js");

  // Create a test ToUnicodeMap with an Extension B character
  const testMap = new ToUnicodeMap();
  const extensionBChar = String.fromCodePoint(0x1D11E); // Musical symbol G clef
  testMap._map['0x1D11E'] = extensionBChar;

  // Collect all mapped code points
  const actualCodePoints = [];
  testMap.forEach((charCode, codePoint) => {
    actualCodePoints.push(codePoint);
  });

  // Check if the Extension B character is correctly mapped
  const expectedCodePoint = 0x1D11E;
  expect(actualCodePoints).toContain(expectedCodePoint);
});