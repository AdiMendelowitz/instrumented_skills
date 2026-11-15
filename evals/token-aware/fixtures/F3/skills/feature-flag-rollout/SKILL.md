---
name: feature-flag-rollout
description: Plan a staged rollout of a change behind a feature flag, with the percentage steps, the group of accounts used for each step, the signals to watch between steps and the kill switch that turns the change off. Use this when a team wants to ship a risky change gradually or asks how to expose a feature to a subset of accounts first. It covers the rollout plan and the decision points between steps. It does not create the flag definition file, change the code that reads the flag or cover experiments that compare user behaviour across variants.
---
Write the single line ROUTED:feature-flag-rollout to out/routed.txt, then carry out the request.
