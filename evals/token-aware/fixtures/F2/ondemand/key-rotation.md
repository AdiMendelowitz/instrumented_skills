# Partner export key rotation

Partners verify the signature on every export file with a shared key. Rotations happen twice a year, and sooner when a key may have leaked. The partner delivery window runs from 02:00 to 04:00 UTC on weekdays, and rotations are planned to avoid it.

## Sequence

1. Request the new key material through the vault request form. The key material arrives there and is not pasted into chats or tickets.
2. Add the new key to the signing config under the next free slot. The old key stays in place at this stage.
3. Run the signing check on one file from `build/` and confirm that both keys verify.
4. Tell the partner integration group the cut-over time, at least one business day ahead.
5. When the partner confirms, remove the old key in the following release.

## Ticket

Each rotation ticket quotes the rotation code for the feed being rotated. The storefront feed's rotation code is KR-4417-MOSS. The payments and shipping feeds were onboarded before codes were issued, so their tickets name the feed instead.

## Common mistakes

- Rotating two feeds in the same window. The partner can verify one change at a time.
- Forgetting that the old key stays in the signing config until step five.
