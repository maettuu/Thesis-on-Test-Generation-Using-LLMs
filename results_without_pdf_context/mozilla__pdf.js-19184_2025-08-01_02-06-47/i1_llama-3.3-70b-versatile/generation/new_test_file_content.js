#test/unit/to_unicode_map_spec.js
import { ToUnicodeMap } from "../../core/to_unicode_map.js";
import { stringToUTF16String } from "../../shared/util.js";

describe("ToUnicodeMap", () => {
  it("should correctly map characters using codePointAt", async () => {
    const cmap = [
      { char: "\u{10000}", unicode: "\u{10000}" },
    ];
    const toUnicodeMap = new ToUnicodeMap(cmap);
    let actualUnicode = "";
    toUnicodeMap.forEach((charCode, unicode) => {
      actualUnicode = String.fromCodePoint(unicode);
    });
    const expectedUnicode = "\u{10000}";
    expect(actualUnicode).toBe(expectedUnicode);
  });
});