import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException


app = FastAPI(
    title="Canada B2B Pipeline API",
    version="1.0.0",
)

PROJECT_ROOT = Path(__file__).resolve().parent
PIPELINE_SCRIPT = PROJECT_ROOT / "run_pipeline.py"

pipeline_lock = threading.Lock()

pipeline_status = {
    "state": "idle",
    "started_at": None,
    "finished_at": None,
    "return_code": None,
    "message": "Pipeline has not been triggered yet.",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def execute_pipeline():
    pipeline_status["state"] = "running"
    pipeline_status["started_at"] = utc_now()
    pipeline_status["finished_at"] = None
    pipeline_status["return_code"] = None
    pipeline_status["message"] = "Pipeline is running."

    try:
        result = subprocess.run(
            [sys.executable, str(PIPELINE_SCRIPT)],
            cwd=PROJECT_ROOT,
            text=True,
        )

        pipeline_status["return_code"] = result.returncode
        pipeline_status["finished_at"] = utc_now()

        if result.returncode == 0:
            pipeline_status["state"] = "completed"
            pipeline_status["message"] = (
                "Pipeline completed successfully."
            )
        else:
            pipeline_status["state"] = "failed"
            pipeline_status["message"] = (
                "Pipeline exited with an error."
            )

    except Exception as exc:
        pipeline_status["state"] = "failed"
        pipeline_status["finished_at"] = utc_now()
        pipeline_status["message"] = str(exc)

    finally:
        pipeline_lock.release()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "canada-b2b-pipeline-api",
    }


@app.get("/pipeline/status")
def get_pipeline_status():
    return pipeline_status


@app.post("/pipeline/run", status_code=202)
def run_pipeline():
    acquired = pipeline_lock.acquire(blocking=False)

    if not acquired:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running.",
        )

    thread = threading.Thread(
        target=execute_pipeline,
        daemon=True,
    )
    thread.start()

    return {
        "accepted": True,
        "message": "Pipeline execution started.",
        "status_endpoint": "/pipeline/status",
    }