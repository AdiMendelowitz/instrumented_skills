---
name: webhook-retry-design
description: Design the retry and dead letter policy for outbound webhook deliveries, including the backoff schedule, the maximum number of attempts, the responses that count as permanent failures and how an operator replays parked deliveries. Use this when a new webhook event type is added or when partners report missed or duplicated deliveries. It covers the policy as a written specification and the failure handling it implies. It does not implement the sending worker, change the signing scheme for payloads or cover inbound webhooks from partners.
---
Write the single line ROUTED:webhook-retry-design to out/routed.txt, then carry out the request.
