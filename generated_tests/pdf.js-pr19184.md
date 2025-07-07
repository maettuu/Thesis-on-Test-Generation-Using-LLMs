## GitHub Pull Request 19184
[[pull request]](https://github.com/mozilla/pdf.js/pull/19184) 
[[linked issue]](https://github.com/mozilla/pdf.js/issues/19182)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
import { ToUnicodeMap } from "../../src/core/to_unicode_map.js";

describe("ToUnicodeMap Extension B Character Rendering", () => {
  it("should correctly map Extension B characters using codePointAt", () => {
    const cmap = { 0x20: "\uD840\uDC00" }; // Example Extension B character
    const toUnicodeMap = new ToUnicodeMap(cmap);

    const expected = 0x20000; // Unicode code point for the character
    let actual;
    toUnicodeMap.forEach((charCode, unicode) => {
      if (charCode === "32") { // 0x20 in decimal
        actual = unicode;
      }
    });

    expect(actual).toBe(expected);
  });
});
```

Our automated pipeline created a new test file `test/unit/to_unicode_map_spec.js` because no fitting file was found. 
The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) ToUnicodeMap Extension B Character Rendering should correctly map Extension B characters using codePointAt
  Message:
    Expected 55360 to be 131072.
  Stack:
        at <Jasmine>
        at UserContext.<anonymous> (file:///app/testbed/build/lib-legacy/test/unit/to_unicode_map_spec.js:38:20)
        at <Jasmine>

Ran 1 of 996 specs
1 spec, 1 failure
Finished in 0.07 seconds
```

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/). \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time.

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/to_unicode_map_spec.js b/to_unicode_map_spec.js
new file mode 100644
index 0000000..aec3f2b
--- /dev/null
+++ b/to_unicode_map_spec.js
@@ -0,0 +1,18 @@
+import { ToUnicodeMap } from "../../core/to_unicode_map.js";
+
+describe("ToUnicodeMap Extension B Character Rendering", () => {
+  it("should correctly map Extension B characters using codePointAt", () => {
+    const cmap = { 0x20: "\uD840\uDC00" }; // Example Extension B character
+    const toUnicodeMap = new ToUnicodeMap(cmap);
+
+    const expected = 0x20000; // Unicode code point for the character
+    let actual;
+    toUnicodeMap.forEach((charCode, unicode) => {
+      if (charCode === "32") { // 0x20 in decimal
+        actual = unicode;
+      }
+    });
+
+    expect(actual).toBe(expected);
+  });
+});
```

</details>