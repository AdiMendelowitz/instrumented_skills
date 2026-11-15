# Kestrel Yard backend working notes

These notes apply to the `yard-services` monorepo. The backend team has six engineers and runs four services: `accounts`, `billing`, `catalogue` and `notify`. The notes describe how we work day to day and why certain habits exist. Where a habit came from an outage, the outage is described beside it.

## Layout

- `services/<name>/` holds the code for one service, including its HTTP handlers and its checks.
- `migrations/` holds schema migrations for the shared database, in one numbered sequence.
- `contracts/` holds the request and response types that services share.
- `gen/` holds code produced by the schema generator.
- `flags/` holds feature flag definitions.
- `config/` holds shared client settings.

We used to keep one migrations folder per service. Two services renumbered the same table in 2024, the release train stopped for a day, and the shared sequence came in afterwards.

## Services

`accounts` owns sign-in and profile data. `billing` owns invoices and payment state. `catalogue` serves product data, read only, to the storefront. `notify` sends email and webhooks on behalf of the other three.

Worked example: a reference code for invoices touches `billing` for the handler, `migrations/` for the new column and `contracts/` for the response type. The team has kept changes like this in one pull request, which keeps the release order simple.

## Hard rules

1. New migration files are named `V<number>__<snake_case_summary>.sql`, where the number is five digits with leading zeros and one more than the highest number already in `migrations/`.

2. Release tags follow `rel/<service>/<YYYY.MM.DD>-<n>`, and the counter `n` starts at 1 each day for each service.

3. Health checks are served at `/_healthz`, never at `/health`. The load balancer already reserves the older path for its own use.

4. Files under `gen/` are regenerated with `make gen` and never edited by hand.

5. Feature flags are defined as YAML files in `flags/` with the keys `name`, `owner` and `retire_by`.

6. Outbound HTTP clients use a timeout of 4250 milliseconds, set under `[client]` in `config/http.toml`.

7. Commit subjects begin with the ticket key `WEB-` followed by the ticket number.

8. Error bodies use the key `err_code`, and the value is an upper case code starting with `E-`.

9. Dropping a column takes two releases: the first release stops reading the column, and the second removes it.

## Soft preferences

- Handlers read more clearly when request parsing sits in its own function. We prefer that layout, but older handlers have not been reshaped.
- Reviewers like a line in the pull request description that names the rollback path. It is a courtesy rather than a gate.
- Helper names in `config/` are easiest to find when they match their section name.

## Releases

Releases have usually gone out on Tuesdays and Thursdays. Hotfixes follow whenever the on-call engineer and the release captain agree. The captain rota lives in the team calendar, and the captain is named in the release channel each morning.

When you are asked to roll back a release, read `ondemand/rollback-runbook.md`, in the folder that holds this file, first.

## Local checks

Each service runs its checks through the make targets, which wrap the same commands the continuous integration system uses. Running a target locally before pushing usually saves a round trip with the pipeline, and the target output is the thing reviewers ask to see.

## Feature flags in practice

Flags were introduced so that the storefront could ship the checkout redesign to a few accounts at a time. Most flags are retired within a quarter, but a handful lived for more than a year because nobody owned the cleanup. The owner field on each flag file came out of that experience. The flag files are read by a small loader at startup, so a flag renamed in the middle of a release looks like a new flag to the loader.

## Migrations in practice

Most migrations are small: a new nullable column, a new index built in the background, or a backfill job that runs after the release. The long ones touch the invoice tables, which are large enough that a plain column change once held a lock for most of an afternoon. Reviewers look hardest at those. The habit of splitting the column add, the code change and the backfill into separate releases came from that afternoon.

## Incident history

In 2023 a single bad image took the notify service down for forty minutes. The rollback had been done by hand, from memory, and the wrong tag was restored. That incident is the reason the rollback path is written down at all.

In 2024 the webhook worker retried every failed delivery without a limit, and one partner's endpoint received thousands of copies of the same event within an hour. The partner asked for an explanation, and the explanation went into the team wiki.

## Onboarding

New engineers usually spend their first week reading the `contracts/` folder and running the make targets for one service. The second week is normally spent on a small change to `catalogue`, which is read only and has the fewest moving parts. Pairing sessions are arranged through the backend lead.

## Memory

The service conventions from the 2025 review are imported here.

@memory/service-conventions.md

Those conventions were agreed across all four services and change less often than this file.

## Shared client settings

Before the shared client settings existed, each service picked its own timeout, and the storefront saw three different values for the same upstream call. The shared file fixed that. It is also where the retry budget for each upstream lives, which the webhook work will need to read.

## History

The first release tags were version numbers, such as `v1.4.0`. They were replaced in 2023 when two services tagged different commits with the same number, and the old tags were left in place for reference.

## Contacts

The backend lead is Rhiannon Oduya. The release captain rota is maintained by Tomas Baptiste, who also keeps the on-call schedule.
