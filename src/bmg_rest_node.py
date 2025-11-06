"""
REST-based node for BMG microplate readers that interfaces with WEI
"""

from pathlib import Path
from typing import Annotated, Optional

from madsci.common.types.action_types import ActionFailed
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types import (
    Slot,
)
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode

from bmg_interface import BmgCom
from bmg_object_thread import BMGThread

"""
TODOs:

- Something is wrong with passing paths in through the command line args. Only works when default paths are set in BMGNodeConfig
     TASK: make these into Path types, not string and test. Probably the double slash when passing in string is the issue

"""


class BMGNodeConfig(RestNodeConfig):
    """Configuration for the BMG node."""

    output_path: str = "C:\\Users\\RPL\\TEST"
    """Data output directory path for bmg data"""
    db_directory_path: str = "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit"
    """Path to directory where assay protocol files are stored"""
    state_update_interval: Optional[float] = 5.0
    """Interval for updating module state in seconds"""


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

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""

        self.init_resource_templates()
        self.create_resources()

        # start the BMG thread after resources are initialized
        self.bmg_thread = BMGThread(
            resource_client=self.resource_client,
            plate_carrier=self.plate_carrier,
            logger=self.logger,
        )
        self.bmg_thread.start()

    def init_resource_templates(self) -> None:
        """Initialize resource templates for the node module."""

        self.resource_client.create_template(
            resource=Slot(
                resource_class="bmg_plate_nest",
                resource_description="The plate nest for a BMG microplate reader",
            ),
            template_name="bmg_plate_nest",
            description="Template of a BMG microplate reader plate nest",
            tags=["PlateNest", "ANSI/SLAS"],
        )

    def create_resources(self) -> None:
        """Create resources for the node module."""

        self.plate_carrier = self.resource_client.create_resource_from_template(
            "bmg_plate_nest",
            resource_name=f"{self.node_definition.node_name}_plate_nest",
        )

    def state_handler(self) -> None:
        """Periodically check state of BMG device"""
        self.cached_temp1 = None
        self.cached_temp2 = None
        self.cached_temp3 = None

        if self.bmg_thread is None:
            self.logger.log_error("BMG thread is not initialized")
            return
        if self.bmg_thread.is_busy:
            self.node_state = {
                "Temp1 (bottom heating plate)": self.cached_temp1,
                "Temp2 (top heating plate)": self.cached_temp2,
                "Temp3 (optic slide heating plate)": self.cached_temp3,
                "bmg_thread_state": "BUSY",
            }
        else:
            # thread is not busy, query the device
            try:
                response = self.bmg_thread.send_command({"action": "read_temps"})
                temps = response["data"]
                self.cached_temp1 = temps["Temp1"]
                self.cached_temp2 = temps["Temp2"]
                self.cached_temp3 = temps["Temp3"]

                self.node_state = {
                    "Temp1 (bottom heating plate)": temps["Temp1"],
                    "Temp2 (top heating plate)": temps["Temp2"],
                    "Temp3 (optic slide heating plate)": temps["Temp3"],
                    "bmg_thead_state": "READY",
                }
            except Exception as e:
                # Do nothing except log the error if state handler doesn't work
                self.logger.log_error(f"Error in state handler: {e}")

    def shutdown_handler(self) -> None:
        """Called to clean up resources before the node is shut down."""
        try:
            if self.bmg_thread:
                self.bmg_thread.stop()

        except Exception as err:
            self.logger.log_error(f"Error during BMG thread and node shutdown: {err}")

    @action(name="open")
    def open(self) -> None:
        """Opens the BMG plate tray"""

        self.logger.log_info("Opening BMG plate tray")

        # send command to BMG thread
        response = self.bmg_thread.send_command({"action": "plate_out"})

        # interpret response
        if not response["success"]:
            raise Exception(f"Failed to open BMG plate tray: {response['error']}")
        self.logger.log_info("BMG plate tray opened")

    @action(name="close")
    def close(self) -> None:
        """Closes the BMG plate tray"""

        self.logger.log_info("Closing BMG plate tray")

        # send command to BMG thread
        response = self.bmg_thread.send_command({"action": "plate_in"})

        # interpret response
        if not response["success"]:
            raise Exception(f"Failed to close BMG plate tray: {response['error']}")
        self.logger.log_info("BMG plate tray closed")

    @action(name="set_temp")
    def set_temp(self, temp: float) -> None:
        """Sets the temperature on the BMG microplate reader"""

        temp = float(temp)
        if temp in {0.0, 0.1} or 25.0 <= temp <= 45.0:
            # temp input is valid, send the command
            response = self.bmg_thread.send_command(
                {"action": "set_temp", "temp": temp}
            )

            # interpret response
            if not response["success"]:
                self.logger.log_error(f"Error setting temperature: {response['error']}")
                return ActionFailed(
                    errors=[f"Error setting temperature: {response['error']}"]
                )
            return None
        # temp input is not valid (fail action, don't put node in error state)
        return ActionFailed(errors=["Invalid temperature input value"])

    @action(name="run_assay")
    def run_assay(
        self,
        assay_name: str,
        data_output_file_name: Annotated[
            Optional[str],
            "data output file name (ex. data.txt). Will default to <timestamp>.txt (ex. 1731706249.txt) if no file name is entered.",
        ] = None,
    ) -> Annotated[Path, "Data .txt file returned by the BMG microplate reader"]:
        """Runs an assay on the BMG plate reader"""

        # run the assay, collect response containting output data file name
        response = self.bmg_thread.send_commmand(
            {
                "action": "run_assay",
                "protocol_name": assay_name,
                "protocol_database_path": self.config.db_directory_path,
                "data_output_directory": self.config.output_path,
                "data_output_file_name": data_output_file_name,
            }
        )

        # interpret response
        if not response["success"]:
            self.logger.log_info(f"Error running assay: {response['error']}")
            return ActionFailed(errors=[f"Error running assay: {response['error']}"])
        return Path(response["data"])


if __name__ == "__main__":
    bmg_node = BMGNode()
    bmg_node.start_node()
