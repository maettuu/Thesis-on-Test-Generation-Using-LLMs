#test/unit/to_unicode_map_spec.js
import { ToUnicodeMap } from "../../core/to_unicode_map.js";

describe("ToUnicodeMap Extension B Character Rendering", () => {
  it("should correctly map Extension B characters using codePointAt", async () => {
    const cmap = { 0x20: "\uD840\uDC00" }; // Example Extension B character
    const toUnicodeMap = new ToUnicodeMap(cmap);

    const expected = 0x20000; // Unicode code point for the character
    let actual;

    toUnicodeMap.forEach((charCode, unicode) => {
      if (charCode === "32") { // 0x20 in decimal
        actual = unicode;
      }
    });

    if (actual === undefined) {
      throw new Error("Character code not found in map.");
    }

    if (actual !== expected) {
      throw new Error(`Expected ${expected}, but got ${actual}.`);
    }
  });
});