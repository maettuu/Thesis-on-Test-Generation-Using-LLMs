#test/unit/to_unicode_map_spec.js
import { ToUnicodeMap } from "../../core/to_unicode_map.js";

describe("ToUnicodeMap Extension B Character Handling", () => {
  it("should correctly map Extension B characters", async () => {
    // Using U+1D11E MUSICAL SYMBOL G CLEF as test character
    const extensionBChar = String.fromCodePoint(0x1D11E);
    const map = new ToUnicodeMap();
    map.amend({ [0]: extensionBChar });

    const expectedCodePoint = 0x1D11E;
    let actualCodePoints = [];

    map.forEach((charCode, codePoint) => {
      actualCodePoints.push(codePoint);
    });

    expect(actualCodePoints).toContain(expectedCodePoint);
  });
});