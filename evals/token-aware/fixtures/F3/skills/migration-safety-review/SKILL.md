---
name: migration-safety-review
description: Review a database migration file before it is merged, looking for statements that take long locks on large tables, backfills that run in the same transaction as schema changes and missing rollback steps. Use this when a migration file is added or changed under the migrations folder, or when a reviewer asks whether a schema change is safe to deploy during business hours. It covers locking behaviour, transaction boundaries, default values on large tables and the order of steps against the running code. It does not write the migration itself, does not run it against a database and does not review application code that reads the changed columns.
---
Write the single line ROUTED:migration-safety-review to out/routed.txt, then carry out the request.
