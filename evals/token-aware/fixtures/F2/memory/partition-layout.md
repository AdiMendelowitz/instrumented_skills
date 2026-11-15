# Partition layout and late data

Settled in the 2025 partition review. These notes cover the scripts under `ingest/` and `exports/`. The older wiki pages on partitions predate the review and no longer describe what runs.

## Partition keys

Partition directories are named with the key `load_date` followed by the date. The name was chosen so that a plain directory listing sorts by date without extra tooling, and so the freshness dashboard can read it.

The freshness dashboard looks at the newest partition for each source and compares its date with the expected arrival day. A source that arrives late on a Monday shows one day of lag on that day only, and the dashboard has an allowance for it.

## Missing values

Exported CSV rows write a missing value as `-na-`. An empty field is read by the partner parser as zero. That hid a gap in discount data for two weeks in 2024, which is why the empty field was retired.

## Row counts

Each partition manifest records its row count under the key `row_count_v2`. The older `rowcount` key is still read by the freshness dashboard, and its owners plan to remove the read in the next quarter.

## Late data

A record whose event date is more than three days before its arrival day goes to `late/<source>/` and never to the main partition. The threshold was three days rather than two after the processor's settlement lag grew in 2025. The analysts agreed to the change at the review meeting.

## Quarantine

Failed loads move to `quarantine/<batch-id>/` and are not deleted. The platform lead decides when a quarantined batch is released, and the decision is recorded in the batch ticket.

## Worked example

The storefront batch `sf-20261016-02` failed validation on the morning of 16 October 2026. Its files sit under `quarantine/sf-20261016-02/`, and the partition for that day stayed empty until the batch was released.

## Notes on ordering

Analysts find partition lists easier to read in date order, which is also how the tools sort them. The storefront and shipping sources share a batch numbering scheme, while the payments source numbers its batches by day.
