COMMENT_TEMPLATE = """
Hi! 🤖 The test below is automatically generated and could serve as a regression test for this PR because it:
- passes in the new codebase after the PR, and
- fails in the old codebase before the PR.

```javascript
%s
```

If you find this regression test useful, feel free to insert it in your test suite.
Our automated pipeline inserted the test in the `%s` file before running it.

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org).
If you have any suggestions, questions, or simply want to learn more, feel free to contact us at konstantinos.kitsios@uzh.ch and mcastelluccio@mozilla.com.
"""
