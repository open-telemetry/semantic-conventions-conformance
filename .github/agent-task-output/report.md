Replayed the 31 frozen commits in order onto the supplied base.

Resolved the database Gradle settings conflicts by preserving the base branch's
agent-control include while applying the source history's test-client include
and rename.

Focused Python tests passed (10 tests). Focused Java tests and Spotless checks
passed. Secret scanning found no secrets. CodeQL found no Python alerts before
the remaining language analysis timed out.
