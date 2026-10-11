# 0013 — The evening run recovers from missed and interrupted evenings by itself

**Decided.**
- Days still needing the evening jobs are worked out from the notebook's own record of finished evenings.
- A missed evening is caught up (settled and learned) without new decisions, since orders cannot be placed in the past.
- An evening that proposed but was never finalized is finalized the next evening, marked late.
- A run that finds NSE's file not yet out pushes nothing, so the next scheduled run starts cleanly.

**Considered.** Relying on every scheduled run succeeding.

**Why.** GitHub may start scheduled runs late or drop them at busy times ([constraints.md](../design/constraints.md)). The spec says nothing waits for you, so the system must heal itself.
