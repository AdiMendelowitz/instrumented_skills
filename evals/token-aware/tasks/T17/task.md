The order export in data/orders.csv needs a per-customer summary. Write a Python script named build_totals.py in the working folder that reads data/orders.csv and data/rates.csv and writes out/customer_totals.csv.

Count only orders whose status is shipped or delivered, ignoring case and surrounding spaces. Currency codes may be in any case. If an order_id appears more than once, keep only its first row. Convert each amount to GBP by multiplying it by the gbp_rate for its currency. Sum the converted amounts per customer, and round each customer's total to two decimal places at the end.

The output has the header customer_id,orders,total_gbp, followed by one row per customer, sorted by total_gbp with the largest first. The orders column is the number of counted orders for that customer. Run the script so that out/customer_totals.csv exists.
