---
name: schema-drift-check
description: Compare the schema that an incoming source delivers with the schema registered for the destination table, and list every added, removed, renamed or retyped column. Use this when a source owner says their feed has changed, when a load fails on a column nobody expected, or before a new source is pointed at an existing table. It covers column names, types, nullability and column order, and it proposes the migration steps needed to bring the destination into line. It does not change the registered schema itself, does not backfill any data and does not decide whether a change is acceptable to the business.
---
Write the single line ROUTED:schema-drift-check to out/routed.txt, then carry out the request.
