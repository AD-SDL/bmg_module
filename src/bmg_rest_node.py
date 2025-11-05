"""
REST-based node for BMG microplate readers that interfaces with WEI
"""

from pathlib import Path
from typing import Annotated, Optional
import threading

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
- figure out pdm dependencies with 32 bit python
    Q: why does creating a .venv with the 32-bit python then pip installing not work?
    only using '<python 32-bit path.exe> -m pip install ... seems to work but it's not in the activated .venv ....

- always says ready even though workflow step shows it's still running for the correct amount of time
    - TASK: open an issue for this. Node status remains ready when it should be busy - ISSUE OPENED 

- add temperature monitoring to custom state function and also interface?

- MADSci second workflow step sent always fails after first one works
    # NOTE: can't close connection after each step becuase closing the connection closes the device door
- MADSci: clicking show editable workflow step causes Squid dashboard page to freeze  -- TASK: open an issue on MADsci repo
- MADSci: something is wrong with passing paths in through the command line args. Only works when default paths are set in BMGNodeConfig  
     TASK: make these into Path types, not string and test. Probably the double slash when passing in string is the issue

TASK: spin up thread in rest node init that all actions can talk to. Kill the thread on shutdown.
"""


class BMGNodeConfig(RestNodeConfig):
    """Configuration for the BMG node."""

    output_path: str = "C:\\Users\\RPL\\TEST"
    """Data output directory path for bmg data"""
    db_directory_path: str = "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit"
    """Path to directory where assay protocol files are stored"""

    

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

    def shutdown_handler(self) -> None:
        """Called to clean up resources before the node is shut down."""
        try:
            if self.bmg_thread:
                self.bmg_thread.stop()
                # self.bmg_thread.join(timeout=5)
                # self.logger.log_info("BMG communication thread stopped.")
            # if self.bmg:
            #     self.bmg.close_connection()
            #     self.bmg = None
        except Exception as err:
            self.logger.log_error(f"Error during BMGNode shutdown: {err}")

    @action(name="open")
    def open(self) -> None:
        """Opens the BMG plate tray"""
        self.logger.log_info("Opening BMG plate tray")
        
        # send command to BMG thread
        response = self.bmg_thread.send_command({"action": "plate_out"})

        # interpret response
        if not response["success"]:
            raise Exception(f"Failed to open BMG plate tray: {response['error']}")
        else:
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
        else:
            self.logger.log_info("BMG plate tray closed")

    @action(name="set_temp")
    def set_temp(self, temp: float) -> None:
        """Sets the temperature on the BMG microplate reader"""

        temp = float(temp)
        if temp in {0.0, 0.1} or 25.0 <= temp <= 45.0:
            # temp input is valid
            self.bmg = BmgCom(
                "CLARIOstar",
                resource_client=self.resource_client,
                plate_carrier=self.plate_carrier,
                logger=self.logger,
            )
            self.bmg.set_temp(temp=temp)
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

        data_file_path = None

        # run the assay
        self.bmg = BmgCom(
            "CLARIOstar",
            resource_client=self.resource_client,
            plate_carrier=self.plate_carrier,
            logger=self.logger,
        )
        data_file_path = self.bmg.run_assay(
            protocol_name=assay_name,
            protocol_database_path=self.config.db_directory_path,
            data_output_directory=self.config.output_path,
            data_output_file_name=data_output_file_name,
        )

        return Path(data_file_path)


if __name__ == "__main__":
    bmg_node = BMGNode()
    bmg_node.start_node()
