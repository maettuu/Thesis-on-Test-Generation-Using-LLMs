## GitHub Pull Request 18306
[[pull request]](https://github.com/mozilla/pdf.js/pull/18306) 
[[linked issue]](https://bugzilla.mozilla.org/show_bug.cgi?id=1903731)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
it("should correctly render PDF with non-integer DW", async () => {
  const { PartialEvaluator } = await import("../../src/core/evaluator.js");
  const { Dict, Name } = await import("../../src/core/primitives.js");
  const { XRefMock } = await import("./test_utils.js");

  const xref = new XRefMock([]);
  const dict = new Dict(xref);
  dict.set("DW", 500.5);
  dict.set("W", [0, 100, 200, 300]);

  const evaluator = new PartialEvaluator({
    xref,
    handler: null,
    pageIndex: 0,
    idFactory: createIdFactory(0),
    fontCache: new Map(),
    builtInCMapCache: new Map(),
    standardFontDataCache: new Map(),
    globalImageCache: new Map(),
    systemFontCache: new Map(),
  });

  const properties = { composite: true };
  evaluator.extractWidths(dict, null, properties);

  expect(properties.defaultWidth).toBe(501);
});
```

Our automated pipeline inserted the test at the end of the `test/unit/evaluator_spec.js` file before running it. 
The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) evaluator should correctly render PDF with non-integer DW
  Message:
    Expected 1000 to be 501.
  Stack:
        at <Jasmine>
        at UserContext.<anonymous> (file:///app/testbed/build/lib-legacy/test/unit/evaluator_spec.js:329:37)

Ran 1 of 975 specs
1 spec, 1 failure
Finished in 0.07 seconds
```

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/). \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time.

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/evaluator_spec.js b/evaluator_spec.js
index 3edc9a8..66595ca 100644
--- a/evaluator_spec.js
+++ b/evaluator_spec.js
@@ -414,4 +414,32 @@ describe("evaluator", function () {
       expect(operatorList.length).toEqual(0);
     });
   });
+
+  it("should correctly render PDF with non-integer DW", async () => {
+    const { PartialEvaluator } = await import("../../core/evaluator.js");
+    const { Dict, Name } = await import("../../core/primitives.js");
+    const { XRefMock } = await import("./test_utils.js");
+
+    const xref = new XRefMock([]);
+    const dict = new Dict(xref);
+    dict.set("DW", 500.5);
+    dict.set("W", [0, 100, 200, 300]);
+
+    const evaluator = new PartialEvaluator({
+      xref,
+      handler: null,
+      pageIndex: 0,
+      idFactory: createIdFactory(0),
+      fontCache: new Map(),
+      builtInCMapCache: new Map(),
+      standardFontDataCache: new Map(),
+      globalImageCache: new Map(),
+      systemFontCache: new Map(),
+    });
+
+    const properties = { composite: true };
+    evaluator.extractWidths(dict, null, properties);
+
+    expect(properties.defaultWidth).toBe(501);
+  });
 });
```

</details>