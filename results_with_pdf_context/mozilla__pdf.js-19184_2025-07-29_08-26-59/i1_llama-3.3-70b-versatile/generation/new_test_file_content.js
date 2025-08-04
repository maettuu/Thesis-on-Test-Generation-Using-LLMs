#test/unit/to_unicode_map_spec.js
import { ToUnicodeMap } from "../../core/to_unicode_map.js";
import { stringToUTF16String } from "../../shared/util.js";

describe("ToUnicodeMap", () => {
  it("should correctly map Extension B characters", async () => {
    const cmap = {
      "0x10000": "\uD800\uDC00", // Example Extension B character
    };
    const toUnicodeMap = new ToUnicodeMap(cmap);
    let actualCharCode;
    let actualUnicodeCodePoint;

    toUnicodeMap.forEach((charCode, unicodeCodePoint) => {
      actualCharCode = charCode;
      actualUnicodeCodePoint = unicodeCodePoint;
    });

    const expectedCharCode = "0x10000";
    const expectedUnicodeCodePoint = 0x10000;

    expect(actualCharCode).toBe(expectedCharCode);
    expect(actualUnicodeCodePoint).toBe(expectedUnicodeCodePoint);
  });
});