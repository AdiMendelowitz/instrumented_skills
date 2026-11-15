# Data card: token-aware evaluation package

What this is: the pre-registration, tasks, fixtures, probes, harness and analysis source, and the 1,788 run records of the token-aware M2 final batch (13 batches run on 2026-11-10 with Claude Code 2.1.303 and claude-sonnet-5-5), with the analysis output and the results file final.md.

Files: 478 published files; 9 changed by redaction; 8999 replacements in total.

Records: `s4/s4final-records-2026-11-10.jsonl.gz`, one JSON record per line, 600 track B runs (12 held-out tasks, arms N, K0, K1, K0f, K1f, 10 runs each) and 18 track A runs (fixture F2, arms AN, AS, ASn, 6 each). Rerun the analysis with `python analysis.py <folder of *.record.json files> prereg.json --stage final --json out.json`; split the records into one file per `run_id` first.

Redaction: the account user name in Windows paths was replaced with `REDACTED_USER` by `publish_eval.py`, in code and records alike. The pre-registered md5s (harness.py, runlib.py, prereg.json, the record sums) therefore do not verify against these copies; `REDACTION-PAIRS.tsv` gives, for every changed file, its original md5 and its published md5. Unchanged files keep their original bytes, listed in `SHA256SUMS`.

Excluded: raw stream logs, earlier batches, pilot data, build briefs and editor backups.

Not measured: Cowork behaviour (untested); the live configuration of any user; fixture F1.

Licence: data under CC BY 4.0 (`LICENSE-DATA.md`); code under the repository's MIT licence.
