# Search cache change: working note
## Purpose
This note records the change to the query cache in the search service and what the team saw afterwards.

## What changed
The query cache moved from a per-process dictionary to a shared store.
Entries now expire after ten minutes instead of never.
The cache key now includes the user locale.

## What we saw
Latency fell 43% after the change.
Cache hit rate rose during the first week and then levelled off.
Memory use per process dropped because the dictionary no longer grows without limit.

## Open questions
Does the ten-minute expiry suit the product catalogue, which changes hourly?
Should the locale be part of the key for anonymous visitors?
Who owns the shared store when it needs an upgrade?

## Next steps
Add an alert on hit rate falling below the level seen in week one.
Write a short runbook for flushing the shared store.
Review the expiry value once a month has passed.

## Owners
Cache change: platform team.
Alerting: operations.
Runbook: platform team.

End of note.
