"""FastAPI sidecar exposing the BMG ActiveX COM connection over HTTP.

This service is intended to run in 32-bit Python because the
BMG_ActiveX.BMGRemoteControl COM server is a 32-bit in-proc server. The MADSci
bmg_module REST node runs in 64-bit Python and talks to this sidecar over
loopback. A single threading.Lock serializes COM access; uvicorn is run with
workers=1 for the same reason.
"""

import argparse
import concurrent.futures
import logging
import queue
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Callable, TypeVar

import pythoncom
import uvicorn
from bmg_interface import BmgCom
from fastapi import FastAPI, HTTPException
from pydantic_models import RunAssayRequest, SetTempRequest

logger = logging.getLogger("bmg_sidecar")

STOP = object()
T = TypeVar("T")


class ComWorker:
    """Worker thread that manages a single BmgCom instance and processes function calls from a queue."""

    def __init__(self, control_name: str, extended_temp_range: bool = False) -> None:
        """Worker thread that manages a single BmgCom instance and processes function calls from a queue."""
        self.control_name = control_name
        self.extended_temp_range = extended_temp_range

        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._ready = threading.Event()

        self._thread.start()
        self._ready.wait()  # block until COM is initialized

    def _run(self) -> None:
        """Worker thread that initializes the COM connection and processes function calls from the queue."""
        pythoncom.CoInitialize()

        try:
            self.bmg = BmgCom(
                control_name=self.control_name,
                extended_temperature_range_model=self.extended_temp_range,
            )

            self._ready.set()

            while True:
                fn, future = self._queue.get()

                if fn is STOP:
                    break

                try:
                    result = fn(self.bmg)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)

        finally:
            try:
                self.bmg.close_connection()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")

            pythoncom.CoUninitialize()

    def call(self, fn: Callable[[BmgCom], T]) -> T:
        """Call a function with the BmgCom instance on the worker thread and return the result."""
        future = concurrent.futures.Future()
        self._queue.put((fn, future))
        return future.result()

    def shutdown(self) -> None:
        """Shut down the worker thread and close the COM connection."""
        self._queue.put((STOP, None))
        self._thread.join()


class _State:
    """Holds the single BmgCom instance and the lock that serializes COM calls."""

    lock: threading.Lock = threading.Lock()
    control_name: str = "CLARIOstar"
    extended_temp_range: bool = False


state = _State()
state.worker = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open the COM connection at startup and close it at shutdown."""
    logger.info(
        "Initializing BmgCom: control=%s extended_temp_range=%s",
        state.control_name,
        state.extended_temp_range,
    )

    # Initialize the ComWorker.
    state.worker = ComWorker(
        control_name="CLARIOstar",
        extended_temp_range=state.extended_temp_range,
    )

    try:
        yield
    finally:
        if state.worker is not None:
            try:
                state.worker.shutdown()
                logger.info("BmgCom connection closed.")
            except Exception as e:
                logger.warning("Error closing BmgCom: %s", e)


app = FastAPI(
    title="bmg_sidecar",
    description="32-bit BMG ActiveX HTTP sidecar",
    lifespan=lifespan,
)


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
    """Return the current status string from the BMG reader."""
    with state.lock:
        return {"status": state.worker.call(lambda bmg: bmg.get_status())}


@app.get("/error")
def error() -> dict:
    """Return the current error message, if any."""
    with state.lock:
        return {"error": state.worker.call(lambda bmg: bmg.get_error())}


@app.get("/temps")
def temps() -> dict:
    """Return dictionary of three current incubator temperatures."""
    with state.lock:
        return state.worker.call(lambda bmg: bmg.read_temps())


@app.post("/plate_out")
def plate_out() -> dict:
    """Move bmg plate carriage out of incubator."""
    with state.lock:
        state.worker.call(lambda bmg: bmg.plate_out())
    return {"ok": True}


@app.post("/plate_in")
def plate_in() -> dict:
    """Move bmg plate carriage into incubator."""
    with state.lock:
        state.worker.call(lambda bmg: bmg.plate_in())
    return {"ok": True}


@app.post("/set_temp")
def set_temp(req: SetTempRequest) -> dict:
    """Set the incubator temperature."""
    with state.lock:
        try:
            state.worker.call(lambda bmg: bmg.set_temp(req.temp))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@app.post("/run_assay")
def run_assay(req: RunAssayRequest) -> dict:
    """Run an assay and return the path to the generated data file."""
    path = state.worker.call(
        lambda bmg: bmg.run_assay(
            assay_name=req.assay_name,
            protocol_database_path=req.protocol_database_path,
            data_output_directory_path=req.data_output_directory_path,
            data_output_file_name=req.data_output_file_name,
            plate_id1=req.plate_id1,
            plate_id2=req.plate_id2,
            plate_id3=req.plate_id3,
        )
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
