# Storefront backfill, partition 16 October 2026

1. Freeze the partition so that no further writes land while it is copied.
2. Copy the frozen partition to the rebuild area.
3. Validate the copy against the source row counts and checksums.
4. Publish the validated copy as the live partition.
