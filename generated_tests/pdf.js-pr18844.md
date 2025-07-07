## GitHub Pull Request 18844
[[pull request]](https://github.com/mozilla/pdf.js/pull/18844) 
[[linked issue]](https://bugzilla.mozilla.org/show_bug.cgi?id=1922063)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
it("should use Calibri and Lucida Console on Windows with Firefox", async () => {
  const { TextLayer } = await import("../../src/display/text_layer.js");
  const { FeatureTest } = await import("../../src/shared/util.js");

  // Mock platform and userAgent
  Object.defineProperty(FeatureTest, "platform", {
    get: () => ({ isWindows: true, isFirefox: true }),
  });

  const fontFamilyMap = TextLayer.fontFamilyMap;
  const expectedSansSerif = "Calibri, sans-serif";
  const expectedMonospace = "Lucida Console, monospace";

  const actualSansSerif = fontFamilyMap.get("sans-serif");
  const actualMonospace = fontFamilyMap.get("monospace");

  expect(actualSansSerif).toBe(expectedSansSerif);
  expect(actualMonospace).toBe(expectedMonospace);
});
```

Our automated pipeline inserted the test at the end of the `test/unit/text_layer_spec.js` file before running it. 
The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) textLayer should use Calibri and Lucida Console on Windows with Firefox
  Message:
    TypeError: Cannot read properties of undefined (reading 'get')
  Stack:
        at UserContext.<anonymous> (file:///app/testbed/build/lib-legacy/test/unit/text_layer_spec.js:228:43)

Ran 1 of 991 specs
1 spec, 1 failure
Finished in 0.071 seconds
```

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/). \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time.

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/text_layer_spec.js b/text_layer_spec.js
index 644e742..237348c 100644
--- a/text_layer_spec.js
+++ b/text_layer_spec.js
@@ -250,4 +250,24 @@ describe("textLayer", function () {
 
     await loadingTask.destroy();
   });
+
+  it("should use Calibri and Lucida Console on Windows with Firefox", async () => {
+    const { TextLayer } = await import("../../display/text_layer.js");
+    const { FeatureTest } = await import("../../shared/util.js");
+
+    // Mock platform and userAgent
+    Object.defineProperty(FeatureTest, "platform", {
+      get: () => ({ isWindows: true, isFirefox: true }),
+    });
+
+    const fontFamilyMap = TextLayer.fontFamilyMap;
+    const expectedSansSerif = "Calibri, sans-serif";
+    const expectedMonospace = "Lucida Console, monospace";
+
+    const actualSansSerif = fontFamilyMap.get("sans-serif");
+    const actualMonospace = fontFamilyMap.get("monospace");
+
+    expect(actualSansSerif).toBe(expectedSansSerif);
+    expect(actualMonospace).toBe(expectedMonospace);
+  });
 });
```

</details>