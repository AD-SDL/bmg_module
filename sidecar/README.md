# bmg_sidecar

32-bit FastAPI HTTP service that owns the `BMG_ActiveX.BMGRemoteControl` COM connection on Windows. The MADSci `bmg_module` node (which runs in 64-bit Python alongside `madsci.common`, whose `psycopg2-binary` transitive dep has no win32 wheel) talks to this sidecar over loopback.

The architecture mirrors `inheco_incubator_module/src/inheco_interface_FastAPI_wrapper.py`: a single hardware singleton protected by `threading.Lock`, one endpoint per BMG operation, no MADSci dependency.

## Run

```powershell
cd C:\Users\RPL\source\repos\bmg_module\sidecar
.venv\Scripts\python.exe bmg_sidecar_server.py --host 127.0.0.1 --port 7002 --control-name CLARIOstar
```

Add `--extended-temp-range` for BMG models that support the 10-60 deg C range.

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET  | `/`          | — | `{"status":"ok","control":...}` |
| GET  | `/is_busy`   | — | `{"busy": bool}` |
| GET  | `/status`    | — | `{"status": str}` |
| GET  | `/error`     | — | `{"error": str}` |
| GET  | `/temps`     | — | `{"Temp1": float, "Temp2": float, "Temp3": float}` |
| POST | `/plate_out` | — | `{"ok": true}` |
| POST | `/plate_in`  | — | `{"ok": true}` |
| POST | `/set_temp`  | `SetTempRequest` | `{"ok": true}` |
| POST | `/run_assay` | `RunAssayRequest` | `{"data_file_path": str}` |

## Requires 32-bit Python

The `BMG_ActiveX.BMGRemoteControl` COM server is a 32-bit in-proc server. Create this venv with a 32-bit Python 3.12 interpreter; `pdm install` will then resolve `comtypes`/`pywin32` against win32.
