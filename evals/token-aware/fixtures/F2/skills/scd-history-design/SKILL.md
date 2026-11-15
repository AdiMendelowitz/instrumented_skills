---
name: scd-history-design
description: Design slowly changing dimension history tables for a dimension whose past values must be kept, including validity start and end columns, a current row indicator and the merge logic that closes superseded rows and opens new ones. Use this when an analyst asks for point in time reporting on customer or product attributes, or when a dimension is about to overwrite values it should keep. It covers the table design and the merge logic written for the transform layer. It does not cover fact table design, the reporting queries that read the history or the retention policy for closed rows.
---
Write the single line ROUTED:scd-history-design to out/routed.txt, then carry out the request.
