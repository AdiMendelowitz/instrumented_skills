# Bundle: multifile

Lens definitions for targets spanning two or more documents that reference each other. Loaded when P2 signature-matches "2+ docs that reference each other". Layers on top of whichever other bundle the individual documents' content would trigger; those lenses still apply per-file.

## Lenses

**cross-file-contradiction**: do the documents agree with each other where they overlap?
Standing checks: the same fact (a rate, a threshold, a version number, a rule) stated in two places with different values; a rule in one file that a template or example in another file violates; a canonical-source claim ("file X owns this fact") contradicted by the fact also being hardcoded elsewhere.

**process archivist**: could a stranger reconstruct the relationship between these files from the files alone?
Standing checks: a cross-reference that names a file that doesn't exist in the set, a dependency between two files that's never stated in either, a "see X for details" that X doesn't actually cover.

**bundle QA** (droppable at cap): internal consistency of the set as a delivered bundle.
Standing checks: version strings that don't match across files that are meant to ship together, an install or setup script that references a file not present in the set, a README describing a file structure the actual files don't match.

## Sequencing

Read files in the order they reference each other where that order is discoverable (a README or index file first, if present). One root cause spanning multiple files is one finding, anchored with a quote or line from each file it touches, not duplicated per file.
