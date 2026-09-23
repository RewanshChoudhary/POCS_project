# Running the two large mixed log samples

Sample 1 has 1,469 valid and 653 invalid sessions. Sample 2 has 546 valid and 167 invalid sessions.
Invalid types (missing `LOGIN`, missing `LOGOUT`, and an event after `LOGOUT`) are shuffled in a
reproducible random order.

## Regenerate the sample logs

```bash
python data/gen_logs.py --mixed-samples-only
```

## Create results for sample 1

This run learns from and evaluates sample 1. Its matching labels are used only for evaluation metrics.

```bash
python report.py \
  --train data/sample_logs.txt \
  --test data/sample_logs.txt \
  --ground-truth data/sample1_ground_truth.csv \
  --export data/results1.json
```

## Create results for sample 2

This run learns from sample 1 and evaluates the independent second sample.

```bash
python report.py \
  --train data/sample_logs.txt \
  --test data/test_logs.txt \
  --ground-truth data/sample2_ground_truth.csv \
  --export data/results2.json
```

## View a result in the static dashboard

```bash
python web/build.py --json data/results1.json --out web/report1.html --serve --port 8000
```

Open `http://localhost:8000/report1.html`.

For sample 2, replace `results1.json` with `results2.json` and `report1.html` with `report2.html`.
