# Ostrander data platform: working agreements

These notes apply to every session in the `ledger-pipelines` repository. The platform team has five engineers and two analysts, and three partners read our exports every day. Most of the rules here exist because a partner once broke, so where a rule has a story behind it, the story sits next to the rule.

## Repository layout

- `ingest/` holds one module per source system. A module owns its landing zone and nothing else.
- `transform/` holds the SQL models and the Python helpers they call.
- `exports/` holds the scripts that write files for partners.
- `legacy_warehouse/` is a frozen snapshot of the old warehouse. Partners still read from it.
- `build/` is scratch space, and anything in it can go at any time.

We used to keep exports beside the transform code. Partners kept picking up half-written files, so exports moved into their own folder in 2025, and the old location sat empty for a quarter before it was removed.

## Sources

The three live sources are the storefront orders feed, the payments processor export and the shipping event stream. Each one has its own ingest module. The payments export arrives a day late in most weeks, which is why the late data notes in the partition file are as detailed as they are.

Worked example: the storefront feed lands through `ingest/src_storefront_orders.py`, writes raw rows into its landing zone and never imports from `transform/`. Reviewers have sent back changes where a transform import slipped into an ingest module, and the fix was always to move the helper somewhere else.

## Hard rules

1. Every CSV written by a script in `exports/` begins with the line `# ostr-export v3`, and the header row follows directly beneath it. The partner parser rejects any file without that line. It was added after a silent column shift in 2024 went unnoticed for a month.

2. Money columns end in `_ct` and hold whole cents. So 19.99 is stored as 1999 in a column called `amount_ct`. Analysts sometimes ask for decimal columns because they read more easily, and the reporting layer does the division for them.

3. Timestamps in exported files are integer epoch milliseconds in UTC. Local times are a presentation concern and do not appear in exports. The shipping export used local time for two years, and the partner's daylight saving handling broke twice.

4. Exports sort their rows by `ledger_id` in ascending order before the file is written. Partners run merge joins on that key and do not sort on their side. The sort is cheap next to a partner rerun.

5. Nothing is written under `legacy_warehouse/`, including temporary files and the output of reruns. Scratch work for a rerun goes to `build/`, which the nightly job clears.

6. A backfill runs in this order: freeze the partition, copy it, validate it, publish it. The order was written down after a backfill published an unchecked partition in 2024.

7. Dates in run manifests are written as `YYYYMMDD` with no separators. The manifest reader slices fixed-width fields, and a dash in a date broke it once already.

8. Parquet outputs are named `<entity>__<YYYYMMDD>__r<run>.parquet`, with two underscores as separators. Analysts search for run numbers by eye, so the pattern is kept deliberately plain.

9. New ingest modules take the `src_` prefix in their file name. Renaming the two older modules is not part of any open ticket.

## Soft preferences

- We prefer snake_case column names. A few older tables still use camelCase, and nobody is asking for them to be renamed.
- Commit messages read best in the imperative mood, though reviewers do not block on tense.
- If you cannot tell which module owns a column, search the repository first. Asking in the channel is fine after that.
- Analysts like a short summary at the top of each export README, with the row count and the run date.

## Rotations and reviews

Keys for partner exports are rotated on a schedule set by the platform lead. The procedure lives in its own file so that this one stays readable.

When you are asked to rotate a partner export signing key, read `ondemand/key-rotation.md`, in the folder that holds this file, first.

The partner integration group usually provides the second reviewer for changes under `exports/`. That group is reachable Monday to Thursday, so changes that land on a Friday usually wait until Monday.

## Local development

The Python helpers run on Python 3.12 inside a virtual environment created from the lock file. The lock file is regenerated after every dependency change, and the platform lead reviews the regenerated file before it is merged. Scratch databases live under `build/` and are rebuilt from the seeds when a session starts, which keeps the seeds the single source for reference data.

## Glossary

- Landing zone: the raw folder an ingest module writes to, before any transform runs.
- Partition: the directory holding one day's rows for one source.
- Backfill: a rebuild of one or more past partitions from the source system.
- Manifest: the small JSON file that describes a partition or a run.
- Late record: a row that arrives well after its event date. The partition notes give the threshold.
- Freeze: the step that stops a partition from changing while it is copied.

## Memory

The partition notes are imported below. They cover the settled rules for keys, missing values, manifests and late data.

@memory/partition-layout.md

The partition notes have been updated more often than this file, and they are the newer source whenever the two differ.

## History

In early 2024 a rounding change in `transform/` moved about a quarter of a percent of revenue between months. The reconciliation took three weeks, and analysts still call it the March problem. Since then, transform pull requests have usually carried before and after row counts in their descriptions.

## Contacts

The platform lead is Dagny Ruud. The partner integration group is run by Oskar Venn, and the analysts' channel is the place to raise anything that is not urgent.
