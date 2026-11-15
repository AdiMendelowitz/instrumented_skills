Table: customer_dim with customer_key, address fields, valid_from, valid_to and is_current.
Merge: close the open row where the address changed by setting valid_to, then insert the new row with valid_from set to the change date, valid_to 9999-12-31 and is_current true.
