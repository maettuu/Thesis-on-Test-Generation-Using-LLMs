COMMENT_TEMPLATE_AMPLIFICATION = """Hi! 🤖 The test below is automatically generated and increases the coverage of this PR because it:
- passes, and
- covers lines that were not covered by the tests introduced in this PR.

```javascript
%s
```

If you find this coverage-increasing test useful, feel free to insert it to your test suite.
Our automated pipeline inserted the test at the end of the `%s` file before running it.


This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org).
If you have any suggestions, questions, or simply want to learn more, feel free to contact us at konstantinos.kitsios@uzh.ch and mcastelluccio@mozilla.com.

<details>
<summary> Click to see which aditional lines were covered.</summary>

```diff
%s
```

Line coverage\\* achieved with developer tests: %0.1f%%
Line coverage\\* achieved with developer & the AI-generated test above: %0.1f%%

\\* Line coverage is calculated over the lines added in this PR.

<details>
"""

COMMENT_TEMPLATE_GENERATION = """Hi! 🤖 The test below is automatically generated and serves as a regression test for this PR because it:
- passes, and
- fails in the codebase before the PR.

```javascript
%s
```

If you find this regression test useful, feel free to insert it to your test suite.
Our automated pipeline inserted the test at the end of the `%s` file before running it.

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org).
If you have any suggestions, questions, or simply want to learn more, feel free to contact us at konstantinos.kitsios@uzh.ch and mcastelluccio@mozilla.com.

<details>
<summary> Click to see which lines were covered.</summary>

```diff
%s
```

Line coverage\\* achieved: %0.1f%%

\\* Line coverage is calculated over the lines added in this PR.

<details>
"""
