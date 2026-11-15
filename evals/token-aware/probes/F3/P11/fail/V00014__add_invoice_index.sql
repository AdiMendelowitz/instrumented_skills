ALTER TABLE invoices ADD COLUMN invoice_ref_v2 TEXT NOT NULL DEFAULT 'none';
CREATE INDEX idx_invoices_ref ON invoices (invoice_ref_v2);
