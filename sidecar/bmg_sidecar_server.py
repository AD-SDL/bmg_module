"""FastAPI sidecar exposing the BMG ActiveX COM connection over HTTP.

This service is intended to run in 32-bit Python because the
BMG_ActiveX.BMGRemoteControl COM server is a 32-bit in-proc server. The MADSci
bmg_module REST node runs in 64-bit Python and talks to this sidecar over
loopback. A single threading.Lock serializes COM access; uvicorn is run with
workers=1 for the same reason.
"""

import argparse
import logging
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException

from bmg_interface import BmgCom
from pydantic_models import RunAssayRequest, SetTempRequest

logger = logging.getLogger("bmg_sidecar")


class _State:
    """Holds the single BmgCom instance and the lock that serializes COM calls."""

    bmg: BmgCom = None
    lock: threading.Lock = threading.Lock()
    control_name: str = "CLARIOstar"
    extended_temp_range: bool = False


state = _State()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the COM connection at startup and close it at shutdown."""
    logger.info(
        "Initializing BmgCom: control=%s extended_temp_range=%s",
        state.control_name,
        state.extended_temp_range,
    )
    state.bmg = BmgCom(
        control_name=state.control_name,
        extended_temperature_range_model=state.extended_temp_range,
    )
    logger.info("BmgCom ready.")
    try:
        yield
    finally:
        if state.bmg is not None:
            try:
                state.bmg.close_connection()
                logger.info("BmgCom connection closed.")
            except Exception as e:
                logger.warning("Error closing BmgCom: %s", e)
            state.bmg = None


app = FastAPI(
    title="bmg_sidecar",
    description="32-bit BMG ActiveX HTTP sidecar",
    lifespan=lifespan,
)


def _require_bmg() -> BmgCom:
    if state.bmg is None:
        raise HTTPException(status_code=503, detail="BMG interface not initialized")
    return state.bmg


@app.get("/")
def root() -> dict:
    """Liveness probe."""
    return {"status": "ok", "control": state.control_name}


@app.get("/is_busy")
def is_busy() -> dict:
    """Return whether the COM lock is currently held by another request."""
    return {"busy": state.lock.locked()}


@app.get("/status")
def status() -> dict:
    bmg = _require_bmg()
    with state.lock:
        return {"status": bmg.get_status()}


@app.get("/error")
def error() -> dict:
    bmg = _require_bmg()
    with state.lock:
        return {"error": bmg.get_error()}


@app.get("/temps")
def temps() -> dict:
    bmg = _require_bmg()
    with state.lock:
        return bmg.read_temps()


@app.post("/plate_out")
def plate_out() -> dict:
    bmg = _require_bmg()
    with state.lock:
        bmg.plate_out()
    return {"ok": True}


@app.post("/plate_in")
def plate_in() -> dict:
    bmg = _require_bmg()
    with state.lock:
        bmg.plate_in()
    return {"ok": True}


@app.post("/set_temp")
def set_temp(req: SetTempRequest) -> dict:
    bmg = _require_bmg()
    with state.lock:
        try:
            bmg.set_temp(req.temp)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@app.post("/run_assay")
def run_assay(req: RunAssayRequest) -> dict:
    bmg = _require_bmg()
    with state.lock:
        path = bmg.run_assay(
            assay_name=req.assay_name,
            protocol_database_path=req.protocol_database_path,
            data_output_directory_path=req.data_output_directory_path,
            data_output_file_name=req.data_output_file_name,
            plate_id1=req.plate_id1,
            plate_id2=req.plate_id2,
            plate_id3=req.plate_id3,
        )
    return {"data_file_path": str(path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7002)
    parser.add_argument("--control-name", default="CLARIOstar")
    parser.add_argument(
        "--extended-temp-range",
        action="store_true",
        help="Enable the 10-60 deg C range supported by extended-range BMG models.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    state.control_name = args.control_name
    state.extended_temp_range = args.extended_temp_range

    uvicorn.run(app, host=args.host, port=args.port, workers=1)
