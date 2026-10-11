# 0008 — PyYAML to read config files

**Decided.** The one third-party package: PyYAML, to read `config/` (your limits, costs, checklists).

**Considered.** Writing config as JSON (no comments, harder for you to read), or a home-made YAML reader.

**Why.** Config is the part of the repo you read and set, so it should be readable with comments. PyYAML is the standard, widely used reader. A home-made one would be cleverness the spec asks us to avoid. This updates 0001 ("standard library first, until a job needs a package").
