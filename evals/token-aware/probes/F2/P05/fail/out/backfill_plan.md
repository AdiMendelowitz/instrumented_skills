# Storefront backfill, partition 16 October 2026

1. Freeze the partition so that no further writes land while it is copied.
2. Copy the frozen partition to the rebuild area.
3. Publish the copy as the live partition.
4. Validate the published partition against the source row counts and checksums.
