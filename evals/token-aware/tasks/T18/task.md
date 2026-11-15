The API request log in data/requests.log holds one request per line: timestamp, method, path, status and latency in milliseconds. Write a Python script named summarise_latency.py that reads it and writes out/latency_summary.json.

Skip blank lines. Treat a path that ends in a slash as the same route as the path without it. Replace every all-digit segment with {id}, so /api/orders/1041 and /api/orders/1042 are one route. A route key is the method, a space, and the normalised path. A latency of n/a is a timeout: count it per route, but leave it out of the latency figures.

For each route, report count (requests with a numeric latency), p50_ms and p95_ms by the nearest-rank method (the value at position ceil(p/100 times n) of the sorted latencies, counting from 1), and timeouts. Write one JSON object keyed by route. Run the script so the output file exists.
