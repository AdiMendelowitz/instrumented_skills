---
name: dq-expectation-writer
description: Write declarative data quality expectations for a table, such as not null checks on keys, uniqueness of identifiers, accepted value ranges and bounds on daily row counts, and give each expectation a severity. Use this when a new table is about to be shared with a partner or when bad values have slipped through a pipeline before. It covers the expectation definitions, their severities and the reason each one exists. It does not run the expectations against live data, does not repair bad values and does not change the load schedule.
---
Write the single line ROUTED:dq-expectation-writer to out/routed.txt, then carry out the request.
