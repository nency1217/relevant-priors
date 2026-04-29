"""HTTP API for the relevant-priors challenge.

POST /predict   — main endpoint, takes a PredictRequest, returns PredictResponse.
GET  /health    — liveness check (returns {"status": "ok"}).
GET  /          — minimal landing page so accidentally-opened browsers don't 404.

Run locally:
    uvicorn app:app --host 0.0.0.0 --port 8000

The server is intentionally stateless across requests except for an in-process
LRU-style cache inside the predictor, which is safe for a single-worker
deployment. For multi-worker setups, switch to a shared cache (Redis) or just
let each worker warm its own cache.
"""
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from models import PredictRequest, PredictResponse
from relevance import HybridPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("relevant-priors")

app = FastAPI(title="Relevant Priors API", version="1.0.0")
predictor = HybridPredictor()


@app.get("/")
def root() -> dict:
    return {
        "service": "relevant-priors",
        "endpoints": {"predict": "POST /predict", "health": "GET /health"},
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    request_id = uuid.uuid4().hex[:8]
    n_cases = len(req.cases)
    n_priors = sum(len(c.prior_studies) for c in req.cases)
    t0 = time.time()
    logger.info(
        "req=%s cases=%d priors=%d challenge_id=%s starting",
        request_id, n_cases, n_priors, req.challenge_id,
    )

    predictions = []
    for case in req.cases:
        predictions.extend(predictor.predict_case(case))

    elapsed = time.time() - t0
    logger.info(
        "req=%s cases=%d priors=%d elapsed=%.3fs predictions=%d",
        request_id, n_cases, n_priors, elapsed, len(predictions),
    )
    return PredictResponse(predictions=predictions)


@app.exception_handler(Exception)
async def unhandled_exc(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all so the evaluator gets a clean error instead of a stack trace."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc)},
    )
