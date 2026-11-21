# Bundle: multifile

Load when the target is 2 or more documents that reference each other.

## archivist
- Two files stating the same fact, with neither marked canonical.
- Content whose last update predates a change it describes.
- Instructions that survived the system they described.
Anchor: both file paths plus the duplicated claim.

## cross-file-contradiction
- Same term defined differently across files.
- Same procedure with different steps or different order.
- A file asserting a constraint another file violates.
Anchor: both quotes, both paths. Contradictions with only one side quoted are dropped.

## sequencing (cross-file)
- Reading order implied but never stated.
- A file that assumes another has been read, with no pointer to it.
- Onboarding paths with an unreachable first step.

## integration (cross-file)
- Links and paths that no longer resolve.
- A file describing an interface that its counterpart file defines differently.
Anchor: the link plus the target that fails to resolve.

## Consolidation rule
When merging duplicates, name the canonical copy and reduce the others to a pointer. Never delete both sides of a contradiction; resolve it or raise it.