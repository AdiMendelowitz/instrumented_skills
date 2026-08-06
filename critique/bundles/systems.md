# Bundle: systems

Lens definitions for architecture and design documents. Loaded when P2 signature-matches "architecture or design doc". The finance section alone is loaded when money, estimates, or SLAs are present regardless of overall signature.

## Lenses

**tech lead / architect**: structure, maintainability, operability.
Standing checks: what will be hardest to change in six months and whether that was chosen or drifted into, a shortcut that has quietly become load-bearing, a single-ownership boundary that's violated somewhere in the design.

**integration** (droppable at cap): behaviour at system boundaries.
Standing checks: an external dependency with no stated failure mode, a retry or timeout policy left unstated, an assumption about ordering or consistency the design needs but never states.

**bundle QA** (droppable at cap): internal consistency of the document set itself, when this bundle loads alongside others.
Standing checks: a diagram that disagrees with the prose describing it, a component named in one section and never again, a version or date on one part of the document that's stale relative to another.

## Finance section

Loaded independently whenever money, estimates, or SLAs appear in the target, regardless of the overall signature.

**finance**: cost, ROI, opportunity cost, and whether a dollar figure is earned rather than assumed.
Standing checks: a cost or saving stated without a rate, date, and source; a dollar figure invented for work that isn't actually billed at a per-unit rate (flag explicitly if the document conflates a subscription or fixed-cost resource with a metered one); an SLA or estimate with no stated basis for how it was derived; a "should save X%" claim with no baseline measurement behind it.

## Always-on additions for systems targets

pre-mortem extends to: which single-point-of-failure in the design is most likely to be the actual cause, not a plausible-sounding one.
red-team extends to: which stated assumption, if wrong, invalidates the largest part of the design.
