import asyncio
import time
from datetime import datetime
from contextlib import asynccontextmanager

import httpx
import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Gauge,
    generate_latest,
)
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression

PROMETHEUS_URL = "http://prometheus:9090"
ANALYSIS_INTERVAL = 60
HISTORY_HOURS = 1

ml_anomaly_score = Gauge(
    "ml_anomaly_score",
    "Anomaly score from IsolationForest (higher = more anomalous)",
    ["metric_name"],
)
ml_anomaly_detected = Gauge(
    "ml_anomaly_detected",
    "1 if anomaly detected by ML model, 0 otherwise",
    ["metric_name"],
)
ml_disk_hours_remaining = Gauge(
    "ml_disk_hours_remaining",
    "Predicted hours until disk is full (linear regression). 9999 = not filling.",
)
ml_predicted_value = Gauge(
    "ml_predicted_value",
    "Predicted value in 5 minutes (linear extrapolation)",
    ["metric_name"],
)
ml_training_samples = Gauge(
    "ml_training_samples",
    "Number of time-series samples used for the last model training",
    ["metric_name"],
)
ml_last_run_timestamp = Gauge(
    "ml_last_analysis_timestamp",
    "Unix timestamp of the last successful ML analysis run",
)

_predictions_cache: dict = {}


async def fetch_range(query: str, hours: float = HISTORY_HOURS) -> list[float]:
    end = time.time()
    start = end - hours * 3600
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={"query": query, "start": start, "end": end, "step": "15s"},
            )
            resp.raise_for_status()
            results = resp.json().get("data", {}).get("result", [])
            if results:
                return [float(v[1]) for v in results[0]["values"]]
    except Exception as exc:
        print(f"[Prometheus fetch error] {exc}")
    return []


def run_isolation_forest(values: list[float]) -> tuple[float, bool]:
    X = np.array(values).reshape(-1, 1)
    clf = IsolationForest(contamination=0.1, random_state=42, n_estimators=50)
    clf.fit(X)
    latest = X[-1].reshape(1, -1)
    score = float(-clf.decision_function(latest)[0])
    is_anomaly = clf.predict(latest)[0] == -1
    return score, bool(is_anomaly)


def predict_in_5min(values: list[float]) -> float:
    X = np.arange(len(values)).reshape(-1, 1).astype(float)
    y = np.array(values)
    reg = LinearRegression().fit(X, y)
    future_step = np.array([[len(values) + 20]])
    return float(reg.predict(future_step)[0])


def predict_disk_hours(values: list[float]) -> float:
    X = np.arange(len(values)).reshape(-1, 1).astype(float)
    y = np.array(values)
    reg = LinearRegression().fit(X, y)
    slope = float(reg.coef_[0])
    current = values[-1]

    if slope >= 0:
        return 9999.0

    steps_remaining = current / abs(slope)
    return round(steps_remaining * 15 / 3600, 2)


METRICS_TO_ANALYZE = {
    "cpu_usage": (
        '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    ),
    "memory_usage": (
        "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"
    ),
    "request_rate": (
        'sum(rate(http_requests_total{job="fastapi"}[5m])) or vector(0)'
    ),
    "response_latency_p95": (
        "histogram_quantile(0.95, "
        "sum(rate(http_request_duration_seconds_bucket{job='fastapi'}[5m])) by (le)"
        ") or vector(0)"
    ),
}


async def analyze():
    results: dict = {}

    for metric_name, query in METRICS_TO_ANALYZE.items():
        values = await fetch_range(query)
        if len(values) < 10:
            print(f"[ML] Недостаточно данных для '{metric_name}' ({len(values)} точек)")
            continue

        score, is_anomaly = run_isolation_forest(values)
        predicted = predict_in_5min(values)

        ml_anomaly_score.labels(metric_name=metric_name).set(score)
        ml_anomaly_detected.labels(metric_name=metric_name).set(int(is_anomaly))
        ml_predicted_value.labels(metric_name=metric_name).set(max(predicted, 0))
        ml_training_samples.labels(metric_name=metric_name).set(len(values))

        results[metric_name] = {
            "current": round(values[-1], 4),
            "predicted_5min": round(max(predicted, 0), 4),
            "anomaly_score": round(score, 4),
            "is_anomaly": is_anomaly,
            "samples_used": len(values),
        }

        status = "ANOMALY" if is_anomaly else "OK"
        print(
            f"[ML] {metric_name}: {values[-1]:.2f} → pred={predicted:.2f} "
            f"score={score:.3f} [{status}]"
        )

    disk_values = await fetch_range(
        'node_filesystem_avail_bytes{mountpoint="/"} / '
        'node_filesystem_size_bytes{mountpoint="/"} * 100',
        hours=6,
    )
    if len(disk_values) >= 10:
        hours_left = predict_disk_hours(disk_values)
        ml_disk_hours_remaining.set(hours_left)
        results["disk_forecast"] = {
            "free_percent_now": round(disk_values[-1], 2),
            "hours_until_full": hours_left if hours_left < 9999 else None,
            "trend": "filling" if hours_left < 9999 else "stable",
        }
    else:
        ml_disk_hours_remaining.set(9999)

    ml_last_run_timestamp.set(time.time())
    _predictions_cache.update(results)
    _predictions_cache["last_updated"] = datetime.now().isoformat()
    print(f"[ML] Анализ завершён: {datetime.now().strftime('%H:%M:%S')}")


async def analysis_loop():
    await asyncio.sleep(30)
    while True:
        await analyze()
        await asyncio.sleep(ANALYSIS_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(analysis_loop())
    yield
    task.cancel()


app = FastAPI(title="ML Anomaly Detection Service", lifespan=lifespan)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/predictions")
async def predictions():
    if not _predictions_cache:
        return JSONResponse(
            content={"status": "warming_up", "message": "Первый анализ ещё не завершён (ждите ~90 сек)"},
            status_code=202,
        )
    return JSONResponse(content={"status": "ok", "data": _predictions_cache})


@app.get("/health")
async def health():
    last_run = _predictions_cache.get("last_updated")
    return {"status": "healthy", "last_analysis": last_run}
