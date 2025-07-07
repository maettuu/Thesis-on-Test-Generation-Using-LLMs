## GitHub Pull Request 19639
[[pull request]](https://github.com/mozilla/pdf.js/pull/19639) 
[[linked issue]](https://github.com/mozilla/pdf.js/issues/19633)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
it("should convert negative line width to absolute value in the graphic state", async () => {
  const { PartialEvaluator } = await import("../../src/core/evaluator.js");
  const { Dict, Name } = await import("../../src/core/primitives.js");
  const { OPS } = await import("../../src/shared/util.js");
  const { createIdFactory } = await import("./test_utils.js");
  // Create a dummy operator list that records operations.
  class DummyOperatorList {
    constructor() {
      this.fnArray = [];
      this.argsArray = [];
    }
    addOp(fn, args) {
      this.fnArray.push(fn);
      this.argsArray.push(args);
    }
    addDependency(dep) {}
    ready = Promise.resolve();
  }
  const opList = new DummyOperatorList();
  // Create a gState with a negative line width.
  const gState = new Map([["LW", -5]]);
  // Create a minimal dummy task.
  const dummyTask = { name: "testTask", ensureNotTerminated() {} };
  // Dummy state manager.
  const dummyStateManager = { state: {} };
  // Minimal caches.
  const localGStateCache = new Map();
  const localColorSpaceCache = new Map();
  // Instantiate PartialEvaluator with dummy parameters.
  const evaluator = new PartialEvaluator({
    xref: { fetch() {} },
    handler: {},
    pageIndex: 0,
    idFactory: createIdFactory(),
    fontCache: new Map(),
    builtInCMapCache: new Map(),
    standardFontDataCache: new Map(),
    globalColorSpaceCache: new Map(),
    globalImageCache: new Map(),
    systemFontCache: new Map(),
    options: {}
  });
  await evaluator.setGState({
    resources: Dict.empty,
    gState,
    operatorList: opList,
    cacheKey: "test",
    task: dummyTask,
    stateManager: dummyStateManager,
    localGStateCache,
    localColorSpaceCache
  });
  // Find the setGState operation and verify that LW has been converted to its absolute value.
  let found = false;
  for (let i = 0; i < opList.fnArray.length; i++) {
    if (opList.fnArray[i] === OPS.setGState) {
      const stateArray = opList.argsArray[i][0];
      for (const entry of stateArray) {
        if (entry[0] === "LW" && entry[1] === 5) {
          found = true;
        }
      }
    }
  }
  expect(found).toBe(true);
});
```

The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) evaluator should convert negative line width to absolute value in the graphic state
  Message:
    Expected false to be true.
  Stack:
        at <Jasmine>
        at UserContext.<anonymous> (file:///app/testbed/build/lib-legacy/test/unit/evaluator_spec.js:372:19)

Ran 1 of 1015 specs
1 spec, 1 failure
Finished in 0.06 seconds
```

Our automated pipeline inserted the test at the end of the `test/unit/evaluator_spec.js` file before running it. \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time. \
This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/).

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/evaluator_spec.js b/evaluator_spec.js
index 3edc9a8..77d6be5 100644
--- a/evaluator_spec.js
+++ b/evaluator_spec.js
@@ -414,4 +414,71 @@ describe("evaluator", function () {
       expect(operatorList.length).toEqual(0);
     });
   });
+
+  it("should convert negative line width to absolute value in the graphic state", async () => {
+    const { PartialEvaluator } = await import("../../core/evaluator.js");
+    const { Dict, Name } = await import("../../core/primitives.js");
+    const { OPS } = await import("../../shared/util.js");
+    const { createIdFactory } = await import("./test_utils.js");
+    // Create a dummy operator list that records operations.
+    class DummyOperatorList {
+      constructor() {
+        this.fnArray = [];
+        this.argsArray = [];
+      }
+      addOp(fn, args) {
+        this.fnArray.push(fn);
+        this.argsArray.push(args);
+      }
+      addDependency(dep) {}
+      ready = Promise.resolve();
+    }
+    const opList = new DummyOperatorList();
+    // Create a gState with a negative line width.
+    const gState = new Map([["LW", -5]]);
+    // Create a minimal dummy task.
+    const dummyTask = { name: "testTask", ensureNotTerminated() {} };
+    // Dummy state manager.
+    const dummyStateManager = { state: {} };
+    // Minimal caches.
+    const localGStateCache = new Map();
+    const localColorSpaceCache = new Map();
+    // Instantiate PartialEvaluator with dummy parameters.
+    const evaluator = new PartialEvaluator({
+      xref: { fetch() {} },
+      handler: {},
+      pageIndex: 0,
+      idFactory: createIdFactory(),
+      fontCache: new Map(),
+      builtInCMapCache: new Map(),
+      standardFontDataCache: new Map(),
+      globalColorSpaceCache: new Map(),
+      globalImageCache: new Map(),
+      systemFontCache: new Map(),
+      options: {}
+    });
+    await evaluator.setGState({
+      resources: Dict.empty,
+      gState,
+      operatorList: opList,
+      cacheKey: "test",
+      task: dummyTask,
+      stateManager: dummyStateManager,
+      localGStateCache,
+      localColorSpaceCache
+    });
+    // Find the setGState operation and verify that LW has been converted to its absolute value.
+    let found = false;
+    for (let i = 0; i < opList.fnArray.length; i++) {
+      if (opList.fnArray[i] === OPS.setGState) {
+        const stateArray = opList.argsArray[i][0];
+        for (const entry of stateArray) {
+          if (entry[0] === "LW" && entry[1] === 5) {
+            found = true;
+          }
+        }
+      }
+    }
+    expect(found).toBe(true);
+  });
 });
```

</details>