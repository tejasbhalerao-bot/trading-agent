# 0001 — Python 3.9 and up, standard library first

**Decided.** Code targets Python 3.9 and up. No third-party packages until a job needs one; tests use pytest.

**Considered.** Requiring a newer Python, installed through a tool such as uv.

**Why.** Your laptop has Python 3.9 and no Homebrew. The cloud machine's version is unknown until the M0 run. Writing for 3.9 runs on both with nothing to install, and the data check had to run on a fresh machine anyway.
