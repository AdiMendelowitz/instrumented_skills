Statement: ALTER TABLE invoices ADD COLUMN invoice_ref_v2 TEXT NOT NULL DEFAULT 'none'.
Risk: on a large table this takes a long lock and rewrites rows.
Change: add the column as nullable, backfill in a separate step after the release, then set NOT NULL.
