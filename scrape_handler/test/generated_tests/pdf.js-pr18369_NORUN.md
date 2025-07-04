## GitHub Pull Request 18369
[[pull request]](https://github.com/mozilla/pdf.js/pull/18369) 
[[linked issue]](https://bugzilla.mozilla.org/show_bug.cgi?id=1905623)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
it("should use vertical variant of a char when its in a missing vertical font", async () => {
  const { Font } = await import("../../src/core/fonts.js");
  const { getVerticalPresentationForm } = await import("../../src/core/fonts_utils.js");

  const properties = {
    loadedName: "TestFont",
    isType3Font: false,
    flags: 0,
    differences: [],
    defaultEncoding: [],
    widths: [],
    defaultWidth: 0,
    composite: false,
    cMap: null,
    capHeight: 0,
    ascent: 0,
    descent: 0,
    fontMatrix: [],
    bbox: [],
    defaultEncoding: [],
    toUnicode: new Map(),
    vertical: true,
    vmetrics: [],
    defaultVMetrics: [],
  };

  const font = new Font("TestFont", null, properties);
  font.missingFile = true;

  const charcode = 0x3001; // IDEOGRAPHIC COMMA
  const expected = String.fromCharCode(getVerticalPresentationForm()[charcode]);

  const glyph = font._charToGlyph(charcode);
  const actual = glyph.unicode;

  expect(actual).toBe(expected);
});
```

Our automated pipeline inserted the test at the end of the `test/unit/api_spec.js` file before running it. 
The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) api should use vertical variant of a char when its in a missing vertical font
  Message:
    TypeError: getVerticalPresentationForm is not a function
  Stack:
        at UserContext.<anonymous> (file:///app/testbed/build/lib-legacy/test/unit/api_spec.js:3404:42)

Ran 1 of 976 specs
1 spec, 1 failure
Finished in 0.08 seconds
```

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/). \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time.

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/api_spec.js b/api_spec.js
index 44f9de0..6a289da 100644
--- a/api_spec.js
+++ b/api_spec.js
@@ -4588,4 +4588,42 @@ Caron Broadcasting, Inc., an Ohio corporation (“Lessee”).`)
       });
     });
   });
+
+  it("should use vertical variant of a char when its in a missing vertical font", async () => {
+    const { Font } = await import("../../core/fonts.js");
+    const { getVerticalPresentationForm } = await import("../../core/fonts_utils.js");
+
+    const properties = {
+      loadedName: "TestFont",
+      isType3Font: false,
+      flags: 0,
+      differences: [],
+      defaultEncoding: [],
+      widths: [],
+      defaultWidth: 0,
+      composite: false,
+      cMap: null,
+      capHeight: 0,
+      ascent: 0,
+      descent: 0,
+      fontMatrix: [],
+      bbox: [],
+      defaultEncoding: [],
+      toUnicode: new Map(),
+      vertical: true,
+      vmetrics: [],
+      defaultVMetrics: [],
+    };
+
+    const font = new Font("TestFont", null, properties);
+    font.missingFile = true;
+
+    const charcode = 0x3001; // IDEOGRAPHIC COMMA
+    const expected = String.fromCharCode(getVerticalPresentationForm()[charcode]);
+
+    const glyph = font._charToGlyph(charcode);
+    const actual = glyph.unicode;
+
+    expect(actual).toBe(expected);
+  });
 });
```

</details>