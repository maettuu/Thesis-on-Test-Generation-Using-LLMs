## GitHub Pull Request 17795
[[pull request]](https://github.com/mozilla/pdf.js/pull/17795) 
[[linked issue]](https://github.com/mozilla/pdf.js/issues/17794)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
it("should not render corrupted inlined images", async () => {
  const { PartialEvaluator } = await import("../../src/core/evaluator.js");
  const { Stream } = await import("../../src/core/stream.js");
  const { Dict } = await import("../../src/core/primitives.js");
  const { OperatorList } = await import("../../src/core/operator_list.js");
  const { OPS } = await import("../../src/shared/util.js");

  const xref = null;
  const resources = Dict.empty;
  const imageStream = new Stream(new Uint8Array([0x00, 0x01, 0x02]));
  const imageDict = new Dict(xref);
  imageDict.set("W", 1);
  imageDict.set("H", 1);
  imageStream.dict = imageDict;
  const operatorList = new OperatorList();
  const evaluator = new PartialEvaluator({
    xref,
    handler: null,
    pageIndex: 0,
    idFactory: null,
    fontCache: null,
    builtInCMapCache: null,
    standardFontDataCache: null,
    globalImageCache: null,
    systemFontCache: null,
    options: { ignoreErrors: true },
  });

  await evaluator.buildPaintImageXObject({
    resources,
    image: imageStream,
    isInline: true,
    operatorList,
    cacheKey: null,
    localImageCache: null,
    localColorSpaceCache: null,
  });

  const expected = [];
  const actual = operatorList.fnArray;
  expect(actual).toEqual(expected);
});
```

Our automated pipeline inserted the test at the end of the `test/unit/evaluator_spec.js` file before running it. 
The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) evaluator should not render corrupted inlined images
  Message:
    FormatError: Bits per component missing in image: false
  Stack:
        at BaseExceptionClosure (file:///app/testbed/build/lib-legacy/shared/util.js:383:29)
        at file:///app/testbed/build/lib-legacy/shared/util.js:386:2
        at ModuleJob.run (node:internal/modules/esm/module_job:263:25)
        at async ModuleLoader.import (node:internal/modules/esm/loader:540:24)
        at async Jasmine._loadFiles (/app/testbed/node_modules/jasmine/lib/jasmine.js:142:7)
        at async Jasmine.loadHelpers (/app/testbed/node_modules/jasmine/lib/jasmine.js:137:5)
        at async Jasmine.execute (/app/testbed/node_modules/jasmine/lib/jasmine.js:190:5)
        at async runJasmine (/app/testbed/node_modules/jasmine/lib/command.js:203:5)
        at async Command.run (/app/testbed/node_modules/jasmine/lib/command.js:71:9)

Ran 1 of 961 specs
1 spec, 1 failure
Finished in 0.099 seconds
```

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/). \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time.

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/evaluator_spec.js b/evaluator_spec.js
index 3edc9a8..d7d5a85 100644
--- a/evaluator_spec.js
+++ b/evaluator_spec.js
@@ -414,4 +414,47 @@ describe("evaluator", function () {
       expect(operatorList.length).toEqual(0);
     });
   });
+
+  it("should not render corrupted inlined images", async () => {
+    const { PartialEvaluator } = await import("../../core/evaluator.js");
+    const { Stream } = await import("../../core/stream.js");
+    const { Dict } = await import("../../core/primitives.js");
+    const { OperatorList } = await import("../../core/operator_list.js");
+    const { OPS } = await import("../../shared/util.js");
+
+    const xref = null;
+    const resources = Dict.empty;
+    const imageStream = new Stream(new Uint8Array([0x00, 0x01, 0x02]));
+    const imageDict = new Dict(xref);
+    imageDict.set("W", 1);
+    imageDict.set("H", 1);
+    imageStream.dict = imageDict;
+    const operatorList = new OperatorList();
+    const evaluator = new PartialEvaluator({
+      xref,
+      handler: null,
+      pageIndex: 0,
+      idFactory: null,
+      fontCache: null,
+      builtInCMapCache: null,
+      standardFontDataCache: null,
+      globalImageCache: null,
+      systemFontCache: null,
+      options: { ignoreErrors: true },
+    });
+
+    await evaluator.buildPaintImageXObject({
+      resources,
+      image: imageStream,
+      isInline: true,
+      operatorList,
+      cacheKey: null,
+      localImageCache: null,
+      localColorSpaceCache: null,
+    });
+
+    const expected = [];
+    const actual = operatorList.fnArray;
+    expect(actual).toEqual(expected);
+  });
 });
```

</details>