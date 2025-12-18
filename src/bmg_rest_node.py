"""
REST-based node for BMG microplate readers that interfaces with WEI
"""

from pathlib import Path, WindowsPath
from typing import Annotated, Optional

from madsci.common.types.action_types import ActionFailed
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types import Slot
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
from pydantic.json_schema import SkipJsonSchema

from bmg_interface import BmgCom
from bmg_object_thread import BMGThread


class BMGNodeConfig(RestNodeConfig):
    """Configuration for the BMG node."""

    data_output_directory_path: SkipJsonSchema[WindowsPath] = WindowsPath(
        "C:/Program Files (x86)/BMG/CLARIOstar/User/Data"
    )
    """Data output directory path for bmg data"""
    db_directory_path: SkipJsonSchema[WindowsPath] = WindowsPath(
        "C:/Program Files (x86)/BMG/CLARIOstar/User/Definit"
    )
    state_update_interval: Optional[float] = 5.0
    """Interval for updating module state in seconds"""
    extended_temperature_range_model: bool = False
    """True if your device allows an extended temperature range (10 deg C to 60 deg C)"""


class BMGNode(RestNode):
    """A node to control the BMG VANTAstar microplate reader"""

    bmg: BmgCom = None
    config_model = BMGNodeConfig
    config: BMGNodeConfig = BMGNodeConfig()
    module_version = "0.0.1"

    def __init__(self) -> None:
        """Initializes the BMG node."""
        super().__init__()
        self.bmg_thread = None
        self.cached_temp1 = None
        self.cached_temp2 = None
        self.cached_temp3 = None
        self.cached_device_state = None

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""

        self.init_resource_templates()
        self.create_resources()

        # Start the BMG thread after resources are initialized
        self.bmg_thread = BMGThread(
            extended_temperature_range_model=self.config.extended_temperature_range_model,
            logger=self.logger,
        )
        self.bmg_thread.start()

    def init_resource_templates(self) -> None:
        """Initialize resource templates for the node module."""

        self.resource_client.create_template(
            resource=Slot(
                resource_description="The plate nest for a BMG microplate reader",
            ),
            template_name="bmg.nest",
            description="Template of a BMG microplate reader plate nest",
            tags=["PlateNest", "ANSI/SLAS"],
        )

    def create_resources(self) -> None:
        """Create resources for the node module."""

        self.plate_carrier = self.resource_client.create_resource_from_template(
            template_name="bmg.nest",
            resource_name=f"{self.node_definition.node_name}.nest",
        )

    def collect_current_plate_resource(self) -> str:
        """Collects the resource ID of the labware in the BMG Plate Nest according to the Resource Manager"""
        assay_plate_resource_id = None
        try:
            child_resource = self.resource_client.get_resource(self.plate_carrier).child
            assay_plate_resource_id = (
                child_resource.resource_id if child_resource else None
            )
        except Exception as e:
            # Don't fail the action if the child resource ID cannot be collected
            self.logger.log_error(e)

        return assay_plate_resource_id

    def state_handler(self) -> None:
        """Periodically check state of BMG device"""

        if self.bmg_thread is None:
            self.logger.log_error("BMG thread is not initialized")
            return

        if self.bmg_thread.is_busy:
            self.node_state = {
                "Temp1 (bottom heating plate)": self.cached_temp1,
                "Temp2 (top heating plate)": self.cached_temp2,
                "Temp3 (optic slide heating plate)": self.cached_temp3,
                "bmg_thread_state": "BUSY",
                "bmg_device_state": "busy",
            }

        else:
            # Thread is not busy, query the device
            try:
                # Collect device state
                device_state = self.bmg_thread.send_command({"action": "device_state"})
                if not device_state["success"]:
                    self.cached_device_state = "unknown"
                else:
                    self.cached_device_state = device_state["data"]

            except Exception as e:
                """Do nothing except log the error if collecting device state in the
                state handler doesn't work. We want any running actions to continue or
                for the device to remain ready to receive the next action, regardless
                of our ability to collect this device state data."""
                self.logger.log_error(f"Error collecting device state: {e}")

            """Log if the device returns that it is in an Error state.
            This doesn't stop  """
            if self.cached_device_state == "Error":
                self.logger.log_warning("Device is in an Error state.")

            try:
                # Collect temperature readings
                response = self.bmg_thread.send_command({"action": "read_temps"})
                temps = response["data"]
                self.cached_temp1 = temps["Temp1"]
                self.cached_temp2 = temps["Temp2"]
                self.cached_temp3 = temps["Temp3"]

                self.node_state = {
                    "Temp1 (bottom heating plate)": self.cached_temp1,
                    "Temp2 (top heating plate)": self.cached_temp2,
                    "Temp3 (optic slide heating plate)": self.cached_temp3,
                    "bmg_thead_state": "READY",
                    "bmg_device_state": self.cached_device_state,
                }
            except Exception as e:
                """Do nothing except log the error if collecting temperatures in the
                state handler doesn't work. We want any running actions to continue or
                for the device to remain ready to receive the next action, regardless
                of our ability to collect this temperature data."""
                self.logger.log_error(f"Error collecting device temperatures: {e}")

    def shutdown_handler(self) -> None:
        """Called to clean up resources before the node is shut down."""
        try:
            if self.bmg_thread:
                self.bmg_thread.stop()

        except Exception as err:
            self.logger.log_error(f"Error during BMG thread and node shutdown: {err}")

    @action(name="open")
    def open(self) -> None:
        """Opens the BMG plate tray."""

        self.logger.log_info("Opening BMG plate tray.")

        # Send command to BMG thread
        response = self.bmg_thread.send_command({"action": "plate_out"})

        # Interpret response
        if not response["success"]:
            raise Exception(f"Failed to open BMG plate tray: {response['error']}")
        self.logger.log_info("BMG plate tray opened.")

    @action(name="close")
    def close(self) -> None:
        """Closes the BMG plate tray."""

        self.logger.log_info("Closing BMG plate tray.")

        # Send command to BMG thread
        response = self.bmg_thread.send_command({"action": "plate_in"})

        # Interpret response
        if not response["success"]:
            raise Exception(f"Failed to close BMG plate tray: {response['error']}")
        self.logger.log_info("BMG plate tray closed.")

    @action(name="set_temp")
    def set_temp(
        self,
        temp: Annotated[
            float,
            "Temperature in Celcius. Valid options are 0.0, 0.1, or 25.0 through 45.0 (10.0 through 60.0 for extended temperature range models).",
        ],
    ) -> None:
        """Sets the temperature on the BMG microplate reader."""

        temp = float(temp)
        min_temp, max_temp = (
            (10.0, 60.0)
            if self.config.extended_temperature_range_model
            else (25.0, 45.0)
        )

        if temp in {0.0, 0.1} or min_temp <= temp <= max_temp:
            # Temp input is valid, send the command
            response = self.bmg_thread.send_command(
                {"action": "set_temp", "temp": temp}
            )

            # Interpret response
            if not response["success"]:
                self.logger.log_error(f"Error setting temperature: {response['error']}")
                return ActionFailed(
                    errors=[f"Error setting temperature: {response['error']}"]
                )
            return None
        # Temp input is not valid (fail action, don't put node in error state)
        return ActionFailed(errors=["Invalid temperature input value."])

    @action(name="run_assay")
    def run_assay(
        self,
        assay_name: str,
        data_output_directory_path: Annotated[
            Optional[str],
            "Data output directory path. Path must point to an existing folder. Defaults to 'C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data'",
        ] = None,
        data_output_file_name: Annotated[
            Optional[str],
            "Data output file name (ex. data.txt). Will default to <timestamp>.txt (ex. 1731706249.txt) if no file name is entered.",
        ] = None,
    ) -> Annotated[tuple[Path, str], "Returns (data file path, assay plate ID)"]:
        """Runs an assay on the BMG plate reader"""

        # Collect the resource ID of the assay plate in the BMG reader, if any. None if no assay plate present according to resource manager.
        assay_plate_id = self.collect_current_plate_resource()

        # Collect and validate the data_directory_path
        if data_output_directory_path is None:
            data_output_directory_path = self.config.data_output_directory_path
        else:
            # Check that the directory path exists
            try:
                if not WindowsPath(data_output_directory_path).is_dir():
                    return ActionFailed(
                        f"data_output_directory_path {data_output_directory_path} is not an existing folder"
                    )
            except Exception as e:
                self.logger.log_error(f"data_directory_output_path is invalid: {e}")
                return ActionFailed(f"data_directory_output_path is invalid: {e}")

        # Run the assay, collect response containing output data file name
        try:
            response = self.bmg_thread.send_command(
                {
                    "action": "run_assay",
                    "protocol_name": assay_name,
                    "protocol_database_path": str(self.config.db_directory_path),
                    "data_output_directory_path": str(data_output_directory_path),
                    "data_output_file_name": data_output_file_name,
                }
            )
        except Exception as e:
            self.logger.log_error(f"Error running assay in REST Node. {e}")
            return ActionFailed(errors=[f"Error running assay in REST Node. {e}"])

        # Interpret response
        self.logger.log_debug(f"{response=}")
        if not response["success"]:
            self.logger.log_error(
                f"Error running assay. response['success'] is False. response = {response}"
            )
            return ActionFailed(
                errors=[
                    f"Error running assay. response['success'] is False. response = {response}"
                ]
            )

        # Return the path to the data file and the associated labware ID (or None)
        return (Path(response["data"]), assay_plate_id)


if __name__ == "__main__":
    bmg_node = BMGNode()
    bmg_node.start_node()
