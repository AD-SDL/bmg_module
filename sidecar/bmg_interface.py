"""Python driver for the BMG microplate reader (our model is BMG VANTAstar)."""

import ctypes
import logging
import time
from pathlib import Path
from typing import Any, Optional

import comtypes.client
import pythoncom

logger = logging.getLogger(__name__)


class BmgCom:
    """Communicate with BMG microplate readers via the ActiveX COM interface."""

    def __init__(
        self,
        control_name: str,
        extended_temperature_range_model: bool = False,
    ) -> None:
        """Initialize and open the connection to the BMG plate reader."""
        self.control_name = control_name
        self.extended_temperature_range_model = extended_temperature_range_model

        pythoncom.CoInitialize()
        self.com = comtypes.client.CreateObject("BMG_ActiveX.BMGRemoteControl")
        self.open_connection()

    def open_connection(self) -> None:
        """Open a connection to the BMG plate reader."""
        ep = ctypes.c_char_p(self.control_name.encode("ascii"))
        res = self.com.OpenConnection(ep)
        if res:
            raise Exception(f"OpenConnection failed: {res}")

    def close_connection(self) -> None:
        """Close the connection to the BMG plate reader."""
        res = self.com.CloseConnection()
        if res:
            raise Exception(f"CloseConnection failed: {res}")

    def get_version(self) -> str:
        """Return the BMG instrument version."""
        return self.com.GetVersion()

    def get_status(self) -> str:
        """Return the current status of the BMG plate reader."""
        item = ctypes.c_char_p(b"Status")
        status = self.com.GetInfo(item)
        return status.strip() if isinstance(status, str) else "unknown"

    def get_error(self) -> str:
        """Return any errors on the BMG plate reader."""
        item = ctypes.c_char_p(b"Error")
        status = self.com.GetInfo(item)
        return status.strip() if isinstance(status, str) else "unknown"

    def init(self) -> None:
        """Initialize the BMG plate reader."""
        self._exec("Init")

    def plate_in(self) -> None:
        """Close the plate tray on the BMG plate reader."""
        self._exec("PlateIn")

    def plate_out(self) -> None:
        """Open the plate tray on the BMG plate reader."""
        self._exec("PlateOut")

    def set_temp(self, temp: float) -> None:
        """Set the temperature on the BMG plate reader.

        Valid temp values: 0.0 (off), 0.1 (monitor only), 25.0-45.0 standard,
        10.0-60.0 for extended-temperature-range models.
        """
        min_temp, max_temp = (
            (10.0, 60.0) if self.extended_temperature_range_model else (25.0, 45.0)
        )
        if not min_temp <= temp <= max_temp and temp not in [0.0, 0.1]:
            raise ValueError(
                f"Temp must be a float between {min_temp} and {max_temp}, or 0.0/0.1"
            )

        nominal_temp = str(temp)
        response = self._exec("Temp", nominal_temp)
        if response != 0:
            logger.error("Failed to set temperature. response = %s", response)
            raise Exception(f"Failed to set temperature. response = {response}")

    def read_temps(self) -> dict:
        """Read the three internal temperature sensors.

        Returns a dict with float values in Celsius, or None per-sensor when
        the underlying GetInfo call returns no value (typical when the device
        has not been initialized in SMART Control or the sensor is not yet
        reporting).
        """

        def _parse(name: bytes) -> Optional[float]:
            raw = self.com.GetInfo(ctypes.c_char_p(name))
            try:
                return float(raw) / 10
            except (TypeError, ValueError):
                return None

        return {
            "Temp1": _parse(b"Temp1"),
            "Temp2": _parse(b"Temp2"),
            "Temp3": _parse(b"Temp3"),
        }

    def run_assay(
        self,
        assay_name: str,
        protocol_database_path: str,
        data_output_directory_path: str,
        data_output_file_name: Optional[str] = None,
        plate_id1: int = 1,
        plate_id2: int = 2,
        plate_id3: int = 3,
    ) -> str:
        """Run an assay on the BMG plate reader. Returns the output data file path."""
        if not data_output_file_name:
            data_output_file_name = str(int(time.time())) + ".txt"

        data_file_path = Path(data_output_directory_path) / data_output_file_name

        response = self._exec(
            "Run",
            assay_name,
            str(protocol_database_path),
            str(data_output_directory_path),
            plate_id1,
            plate_id2,
            plate_id3,
            str(data_output_directory_path),
            data_output_file_name,
        )
        if response != 0:
            logger.error("Failed to run assay. response = %s", response)
            raise Exception(f"Failed to run assay. response = {response}")

        return str(data_file_path)

    def _exec(self, cmd: str, *args: Any) -> int:
        """Execute a command over the established BMG connection."""
        args = (cmd, *args)
        response = self.com.ExecuteAndWait(args)
        logger.info("exec response: %s", response)
        return response


if __name__ == "__main__":
    com = BmgCom("CLARIOstar")
    print(f"BMG LABTECH Remote Control Version: {com.get_version()}")  # noqa: T201
