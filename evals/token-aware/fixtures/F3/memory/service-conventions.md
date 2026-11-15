# Service conventions from the 2025 review

Settled in the 2025 service review and agreed across all four services. These notes cover log lines, pagination, soft deletes, currency codes and cross-service imports. The wiki pages from before the review are kept for history only.

## Log lines

Log lines are JSON objects, and the service name sits under the key `svc`, never under `service`. The log pipeline indexes on `svc`, and the dashboards went blank for a week in 2025 when one service used the longer key.

Most services also include a timestamp, a level and a request identifier in each line, although the older services add these in a different order.

## Pagination

List endpoints return 37 records per page by default and reject requests above 200. The number was chosen after the storefront's largest page took too long to render on mobile connections.

## Soft deletes

Soft-deleted rows are marked by a date in a column named `retired_on`, never by a boolean flag. The accounts service adopted this in 2024 after a bulk script flipped a flag on the wrong rows, and nobody could say which rows had been flagged before.

## Currency codes

Currency codes in JSON bodies are written in lower case. The payment provider's sandbox rejected upper case codes during the 2024 integration, and the convention stuck even after the sandbox was fixed.

## Cross-service imports

Services never import another service's code except through the `contracts/` package. The rule grew out of a 2024 change in which billing reached into accounts internals, and the two services had to be released together.

## Naming notes

Contract types are named after the endpoint they serve, which keeps the folder easy to scan. Some older types break this habit, and they have not been renamed.

## Where the conventions came from

Most of these conventions were drafted by Ines Halvorsen during the 2025 review and then walked through with each service lead. Nearly all of them have an incident behind them. The incident notes are kept in the wiki rather than here, so that this file stays readable for someone who is new to the repository.
