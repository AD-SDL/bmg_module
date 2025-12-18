"""
Python Driver for the BMG Microplate Reader (our model is BMG VANTAstar)
"""

import ctypes
import time
from pathlib import Path
from typing import Any, Optional

import comtypes.client
import pythoncom
from madsci.client.event_client import EventClient


class BmgCom:
    """Class to communicate with BMG microplate readers via ActiveX COM interface."""

    def __init__(
        self,
        control_name: str,
        extended_temperature_range_model: bool,
        logger: EventClient = None,
    ) -> None:
        """Initializes and opens the connection the BMG plate reader"""

        self.control_name = control_name
        self.extended_temperature_range_model = extended_temperature_range_model
        self.logger = logger or EventClient()

        pythoncom.CoInitialize()
        self.com = comtypes.client.CreateObject("BMG_ActiveX.BMGRemoteControl")
        self.open_connection()

    def open_connection(self) -> None:
        """Opens a connection to the BMG plate reader"""
        ep = ctypes.c_char_p(self.control_name.encode("ascii"))
        res = self.com.OpenConnection(ep)
        if res:
            raise Exception(f"OpenConnection failed: {res}")

    def close_connection(self) -> None:
        """Closes the connection to the BMG plate reader"""
        res = self.com.CloseConnection()
        if res:
            raise Exception(f"CloseConnection failed: {res}")

    def get_version(self) -> str:
        """Returns the BMG instrument version"""
        return self.com.GetVersion()

    def get_status(self) -> str:
        """Returns the current status of the BMG plate reader"""
        item = ctypes.c_char_p(b"Status")
        status = self.com.GetInfo(item)
        return status.strip() if isinstance(status, str) else "unknown"

    def get_error(self) -> str:
        """Returns any errors on the BMG plate reader"""
        item = ctypes.c_char_p(b"Error")
        status = self.com.GetInfo(item)
        return status.strip() if isinstance(status, str) else "unknown"

    def init(self) -> None:
        """Initializes the BMG plate reader"""
        self._exec("Init")

    def plate_in(self) -> None:
        """Closes the plate tray on the BMG plate reader"""
        self._exec("PlateIn")

    def plate_out(self) -> None:
        """Opens the plate tray on the BMG plate reader"""
        self._exec("PlateOut")

    def set_temp(self, temp: float) -> None:
        """Sets the temperature on the BMG plate reader.

        Args:
            temp (float): Temperature in Celsius
                Allowed values:
                    00.0 = The incubator unit will be switched off.
                    00.1 = Temperature will not be controlled, but will be monitored.
                    25.0 - 45.0 = Incubator will be switched on and new temp value will be set. Can be changed in increments of 0.1 deg C
                    10.0 - 60.0 = This range is ONLY allowed on extended range models.

        Notes:
            - Will throw get_ code -20 if temp input is not a valid value.
            - Temp must be a float to be valid.
            - If more than one decimal point are included, will round to nearest valid temp input.
        """
        # Check that temperature input is valid. Valid temp range varies by device model.
        min_temp, max_temp = (
            (10.0, 60.0) if self.extended_temperature_range_model else (25.0, 45.0)
        )
        if not min_temp <= temp <= max_temp and temp not in [0.0, 0.1]:
            raise ValueError(
                f"Temp argument must be a valid float between {min_temp} and {max_temp}, or equal to 0.0 or 0.1"
            )

        # Format and execute action
        nominal_temp = str(temp)
        self._exec("Temp", nominal_temp)

    def read_temps(self) -> dict:
        """Reads the temperature at three locations in the BMG plate reader

        Returns: a dictionary of temperature readouts.
            {
                "Temp1": (float temperature reading from bottom heating plate)
                "Temp2": (float temperature reading from top heating plate)
                "Temp3:" (float temperature reading from optic slide heating plate)
            }
        """
        temp1_formatted = ctypes.c_char_p(b"Temp1")
        temp1 = self.com.GetInfo(temp1_formatted)
        temp2_formatted = ctypes.c_char_p(b"Temp2")
        temp2 = self.com.GetInfo(temp2_formatted)
        temp3_formatted = ctypes.c_char_p(b"Temp3")
        temp3 = self.com.GetInfo(temp3_formatted)

        # Convert to floats in Celsius
        temp1 = float(temp1) / 10
        temp2 = float(temp2) / 10
        temp3 = float(temp3) / 10
        return {
            "Temp1": temp1,
            "Temp2": temp2,
            "Temp3": temp3,
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
        """Runs an assay on the BMG plate reader.

        Args:
            assay_name (str): Name of the assay to run, name matches existing protocol name in SMART Control Software.
            protocol_database_path (str): Path to directory where assay protocol files are stored.
            data_output_directory (str): Path to data output directory for bmg data. Must be an existing directory.
            data_output_file_name (str, optional): data output file name (ex. "data.txt").
            plate_id1 (int): Assay will not run without an integer passed in here. It's unclear what this plate_id does.
            plate_id2 (int): Assay will not run without an integer passed in here. It's unclear what this plate_id does.
            plate_id3 (int): Assay will not run without an integer passed in here. It's unclear what this plate_id does.

        Returns:
            data_file_path (str): Path to resulting data file.
        """
        # Give the data file a unique name if no name is specified
        if not data_output_file_name:
            data_output_file_name = str(int(time.time())) + ".txt"

        # Format the data output file name and path
        data_dir = Path(data_output_directory_path)
        data_file_path = data_dir / data_output_file_name

        # Execute run assay command
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
        self.logger.log_info(f"Run action response: {response}")

        return data_file_path

    def is_busy(self) -> bool:
        """Returns True if BMG is busy, False if not busy"""
        return bool(self.lock.locked())

    def _exec(self, cmd: str, *args: Any) -> None:
        """Executed a command over the established connection with the BMG plate reader"""
        args = (cmd, *args)
        response = self.com.ExecuteAndWait(args)
        self.logger.log_info(f"exec response: {response}")
        return response


if __name__ == "__main__":
    com = BmgCom("CLARIOstar")
    print(f"BMG LABTECH Remote Control Version: {com.get_version()}")  # noqa: T201
