#test/unit/to_unicode_map_spec.js
it("should render Extension B characters in form fields correctly", async () => {
  const { ToUnicodeMap } = await import("../../core/to_unicode_map.js");
  const cmap = ["\uA788", "\uA789"];
  const toUnicodeMap = new ToUnicodeMap(cmap);
  const expected = "\uA788".codePointAt(0);
  let actual;
  toUnicodeMap.forEach((charCode, value) => {
    if (charCode === "0") {
      actual = value;
    }
  });
  expect(actual).toBe(expected);
});