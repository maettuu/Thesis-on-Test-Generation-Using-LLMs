## GitHub Pull Request 19716
[[pull request]](https://github.com/mozilla/pdf.js/pull/19716) 
[[linked issue]](https://github.com/mozilla/pdf.js/issues/16742)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
it("should apply the rotated soft mask transform correctly", async () => {
  const { CanvasGraphics } = await import("../../src/display/canvas.js");
  const expectedMatrix = new DOMMatrix().rotate(45);
  const fakeSuspendedCtx = {
    canvas: { width: 100, height: 100 },
    getTransform() { return expectedMatrix; }
  };
  let recordedMatrix = null;
  const fakeNewCtx = {
    canvas: { width: 100, height: 100 },
    setTransform(matrix) { recordedMatrix = matrix; }
  };
  const dummyCachedCanvases = {
    getCanvas(_id, width, height) {
      return { canvas: { width, height }, context: fakeNewCtx };
    }
  };
  const cg = new CanvasGraphics(
    fakeSuspendedCtx,
    {},
    {},
    {},
    {},
    { optionalContentConfig: {} },
    new Map(),
    {}
  );
  cg.cachedCanvases = dummyCachedCanvases;
  cg.beginSMaskMode();
  expect(recordedMatrix).toEqual(expectedMatrix);
});
```

The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) api should apply the rotated soft mask transform correctly
  Message:
    Expected 0.7071067811865476 to equal matrix(0.7071067811865476, 0.7071067811865475, -0.7071067811865475, 0.7071067811865476, 0, 0).
  Stack:
        at <Jasmine>
        at UserContext.<anonymous> (file:///app/testbed/build/lib-legacy/test/unit/api_spec.js:3922:28)
        at process.processTicksAndRejections (node:internal/process/task_queues:95:5)

Ran 1 of 1016 specs
1 spec, 1 failure
Finished in 0.069 seconds
```

Our automated pipeline inserted the test at the end of the `test/unit/api_spec.js` file before running it. \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time. \
This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/).

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/api_spec.js b/api_spec.js
index f8c1006..2f6bd33 100644
--- a/api_spec.js
+++ b/api_spec.js
@@ -5083,4 +5083,36 @@ Caron Broadcasting, Inc., an Ohio corporation (“Lessee”).`)
       }
     );
   });
+
+  it("should apply the rotated soft mask transform correctly", async () => {
+    const { CanvasGraphics } = await import("../../display/canvas.js");
+    const expectedMatrix = new DOMMatrix().rotate(45);
+    const fakeSuspendedCtx = {
+      canvas: { width: 100, height: 100 },
+      getTransform() { return expectedMatrix; }
+    };
+    let recordedMatrix = null;
+    const fakeNewCtx = {
+      canvas: { width: 100, height: 100 },
+      setTransform(matrix) { recordedMatrix = matrix; }
+    };
+    const dummyCachedCanvases = {
+      getCanvas(_id, width, height) {
+        return { canvas: { width, height }, context: fakeNewCtx };
+      }
+    };
+    const cg = new CanvasGraphics(
+      fakeSuspendedCtx,
+      {},
+      {},
+      {},
+      {},
+      { optionalContentConfig: {} },
+      new Map(),
+      {}
+    );
+    cg.cachedCanvases = dummyCachedCanvases;
+    cg.beginSMaskMode();
+    expect(recordedMatrix).toEqual(expectedMatrix);
+  });
 });
```

</details>