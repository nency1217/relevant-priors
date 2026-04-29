# Relevant Priors API

HTTP API for the New Lantern relevant-priors-v1 challenge. Given a current
radiology examination plus a list of prior examinations for the same patient,
predicts which priors a radiologist should see while reading the current.

## How it works

A radiology prior is most useful to compare against the current exam when it
covers the **same anatomy**. We extract canonical body regions and modality
from each `study_description` and predict a prior is relevant when its
regions overlap the current exam's regions — including anatomically adjacent
regions (e.g. chest CT often catches the upper abdomen, so an abdomen prior
can be relevant to a chest current).

This is a deterministic rule-based approach. We deliberately avoid per-prior
LLM calls because, per the challenge hints, that strategy times out on the
private split. The taxonomy lookup is microseconds per pair, so 27k+ priors
finish well under the 360-second evaluator timeout.

Decision pipeline:

1. **Region overlap** — primary signal. Both studies parse to a region set; if
   the sets intersect (or are adjacent), the prior is relevant.
2. **Token-overlap fallback** — if region parsing fails for either side, we
   fall back to set-overlap on cleaned tokens with a 0.4 threshold.
3. **Default-true** — last resort if everything else returns nothing. Skipped
   priors count as incorrect, so we'd rather predict than abstain.
4. **Modality boost** — if regions don't overlap but both studies are mammo
   or DEXA (modalities where serial follow-up is the norm), flip to relevant.

A per-(current_desc, prior_desc) cache means repeated study-pairs across the
27k priors are O(1) on subsequent hits.

## Project layout

```
relevant-priors/
├── app.py                    # FastAPI server
├── models.py                 # Pydantic request/response models
├── relevance/
│   ├── taxonomy.py           # Body-region & modality keyword tables
│   ├── parser.py             # Description -> regions / modality
│   └── predictor.py          # HybridPredictor — main decision logic
├── scripts/eval_local.py     # Run against the public eval JSON
├── tests/test_relevance.py   # Unit tests (12 tests, all pure python)
├── requirements.txt
├── Dockerfile
├── render.yaml               # Render.com blueprint
├── fly.toml                  # Fly.io config
└── experiments.md            # Write-up
```

## Run locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Smoke test:

```bash
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "challenge_id": "relevant-priors-v1",
    "schema_version": 1,
    "cases": [{
      "case_id": "c1",
      "current_study": {"study_id": "s1", "study_description": "CT CHEST WITH CONTRAST"},
      "prior_studies": [
        {"study_id": "p1", "study_description": "CHEST X-RAY 2 VIEWS"},
        {"study_id": "p2", "study_description": "MRI KNEE LEFT"}
      ]
    }]
  }'
```

Expected: p1 → true, p2 → false.

## Run unit tests

```bash
python tests/test_relevance.py
```

## Score against the public eval

Download `public_eval.json` from the challenge page, then:

```bash
python -m scripts.eval_local public_eval.json
```

The script prints overall accuracy, the confusion matrix, and the first
15 mistakes (so you can spot taxonomy gaps to fix).

## Deploy

### Render (easiest)

1. Push this repo to GitHub.
2. In Render: **New +** → **Blueprint** → point at the repo.
3. The free tier sleeps after inactivity; bring it up with a request before
   you submit so the first evaluator hit doesn't pay cold-start latency.

### Fly.io

```bash
fly launch --no-deploy   # accepts the existing fly.toml
fly deploy
fly status               # grab the https URL
```

### Docker (self-host / VPS)

```bash
docker build -t relevant-priors .
docker run -p 8000:8000 relevant-priors
```

Then put it behind any reverse proxy that gives you HTTPS (Caddy is one line:
`example.com { reverse_proxy localhost:8000 }`).

## Endpoints

- `POST /predict` — main scoring endpoint (matches challenge schema)
- `GET /health` — returns `{"status": "ok"}`
- `GET /` — minimal landing page

## Notes on the input schema

Pydantic models accept extra fields and ignore them (`extra="ignore"`), so
schema additions on the evaluator side won't break the contract. Only
`case_id`, `current_study.study_id`, and each `prior_studies[].study_id`
are strictly required to produce a response.
