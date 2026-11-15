---
name: rate-limit-policy
description: Decide the rate limits for a public or partner facing endpoint, including the window size, the limit per key or per account, the status code and headers returned when a caller goes over, and any exemptions for internal callers. Use this when an endpoint is opened to a new partner, when abuse is reported against an existing route or when a limit must change ahead of a launch. It covers the policy values and the reasoning behind each one. It does not implement the limiter in the gateway, handle authentication failures or set quotas for billing plans.
---
Write the single line ROUTED:rate-limit-policy to out/routed.txt, then carry out the request.
