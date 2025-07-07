## GitHub Pull Request 19825
[[pull request]](https://github.com/mozilla/pdf.js/pull/19825) 
[[linked issue]](https://bugzilla.mozilla.org/show_bug.cgi?id=1961107)

The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the post-PR codebase, and
- fails in the pre-PR codebase.

```javascript
it("should apply transformations correctly without subarray creation", async () => {
  const { Util } = await import("../../src/shared/util.js");
  const transform = [1, 0, 0, 1, 10, 20];
  const points = [5, 5, 10, 10];
  const expected = [15, 25, 20, 30];
  Util.applyTransform(points, transform, 0);
  Util.applyTransform(points, transform, 2);
  expect(points).toEqual(expected);
});
```

The test failed on the pre-PR codebase with the following message.

```text
Failures:
1) util should apply transformations correctly without subarray creation
  Message:
    Expected $[0] = 25 to equal 15.
    Expected $[1] = 45 to equal 25.
    Expected $[2] = 10 to equal 20.
    Expected $[3] = 10 to equal 30.
  Stack:
        at <Jasmine>
        at UserContext.<anonymous> (file:///app/testbed/build/lib-legacy/test/unit/util_spec.js:199:20)

Ran 1 of 1016 specs
1 spec, 1 failure
Finished in 0.064 seconds
```

Our automated pipeline inserted the test at the end of the `test/unit/util_spec.js` file before running it. \
Looking forward to see what you think of the test. If you find it useful, we can open a PR. Thanks for your time. \
This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org/).

<details> <summary>Click to see the test patch.</summary>

```diff
diff --git a/util_spec.js b/util_spec.js
index 9d96e11..2e4c8de 100644
--- a/util_spec.js
+++ b/util_spec.js
@@ -257,4 +257,14 @@ describe("util", function () {
       expect(uuid.length).toBeGreaterThanOrEqual(32);
     });
   });
+
+  it("should apply transformations correctly without subarray creation", async () => {
+    const { Util } = await import("../../shared/util.js");
+    const transform = [1, 0, 0, 1, 10, 20];
+    const points = [5, 5, 10, 10];
+    const expected = [15, 25, 20, 30];
+    Util.applyTransform(points, transform, 0);
+    Util.applyTransform(points, transform, 2);
+    expect(points).toEqual(expected);
+  });
 });
```

</details>