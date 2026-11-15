order_id: not null, unique, severity error.
order_value: not null, between 0 and 1000000, severity error.
status: accepted values placed, shipped, cancelled, severity warn.
daily row count: between 0.5 and 2 times the trailing 28-day median, severity warn.
