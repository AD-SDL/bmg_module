"""REST-based MADSci node for BMG microplate readers.

The node delegates all BMG ActiveX COM calls to a separate 32-bit FastAPI
sidecar process (see bmg_module/sidecar/), because madsci.common (v0.8) pulls
in psycopg2-binary, which has no win32 wheel. This file talks to the sidecar
over loopback HTTP, mirroring the pattern used by inheco_incubator_module.
"""

from pathlib import Path
from typing import Annotated, Any, ClassVar, Optional

import requests
from madsci.common.types.action_types import ActionFailed
from madsci.common.types.node_types import (
    NodeIntrinsicLocationDefinition,
    NodeRepresentationTemplateDefinition,
    RestNodeConfig,
)
from madsci.common.types.resource_types import Slot
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode


class BMGNodeConfig(RestNodeConfig):
    """Configuration for the BMG node."""

    data_output_directory_path: Path = Path(
        "C:/Program Files (x86)/BMG/CLARIOstar/User/Data"
    )
    """Data output directory path for bmg data."""
    db_directory_path: Path = Path("C:/Program Files (x86)/BMG/CLARIOstar/User/Definit")
    """Path to the protocol database directory."""
    state_update_interval: Optional[float] = 5.0
    """Interval for updating module state in seconds."""
    extended_temperature_range_model: bool = False
    """True if your device allows an extended temperature range (10-60 deg C)."""

    sidecar_host: str = "127.0.0.1"
    """Host of the 32-bit BMG COM sidecar (typically loopback)."""
    sidecar_port: int = 7002
    """Port the BMG COM sidecar listens on."""
    sidecar_timeout: float = 300.0
    """Per-request timeout (seconds) when talking to the sidecar."""


class BMGNode(RestNode):
    """A node to control the BMG VANTAstar microplate reader."""

    config_model = BMGNodeConfig
    config: BMGNodeConfig = BMGNodeConfig()
    module_version = "0.0.1"

    # Define representation templates and intrinsic locations for the BMG node.
    location_representation_templates: ClassVar[
        list[NodeRepresentationTemplateDefinition]
    ] = [
        NodeRepresentationTemplateDefinition(
            template_name="bmg_carriage_repr",
            default_values={"carriage_type": "standard", "capacity": 1},
            schema_def={
                "type": "object",
                "properties": {
                    "capacity": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of plates the carriage can hold",
                    },
                },
            },
            required_overrides=[],
            tags=["plate_reader", "carriage"],
            version="1.0.0",
            description="BMG carriage representation with capacity",
        ),
    ]
    intrinsic_locations: ClassVar[list[NodeIntrinsicLocationDefinition]] = [
        NodeIntrinsicLocationDefinition(
            location_name="bmg_carriage",
            description="BMG microplate reader carriage.",
            representation_template_name="bmg_carriage_repr",
            resource_template_name="bmg.nest",
            allow_transfers=True,
        ),
    ]

    def __init__(self) -> None:
        """Initializes the BMG node."""
        super().__init__()
        self.cached_temp1 = None
        self.cached_temp2 = None
        self.cached_temp3 = None
        self.cached_device_state = None
        self.cached_current_errors = None

    # ---- Sidecar HTTP helpers -------------------------------------------------

    def _url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return (
            f"http://{self.config.sidecar_host}:{self.config.sidecar_port}/{endpoint}"
        )

    def _get(self, endpoint: str) -> Any:
        response = requests.get(
            self._url(endpoint), timeout=self.config.sidecar_timeout
        )
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, body: Optional[dict] = None) -> Any:
        response = requests.post(
            self._url(endpoint),
            json=body if body is not None else {},
            timeout=self.config.sidecar_timeout,
        )
        response.raise_for_status()
        return response.json()

    # ---- Lifecycle ------------------------------------------------------------

    def startup_handler(self) -> None:
        """Verify the sidecar is reachable and initialize MADSci resources."""
        self._get("/")  # let exception bubble up if sidecar isn't up yet
        self.logger.log_info(
            f"BMG sidecar reachable at {self.config.sidecar_host}:{self.config.sidecar_port}"
        )
        self.init_resource_templates()
        self.create_resources()

    def shutdown_handler(self) -> None:
        """No-op: the sidecar is a separate process managed by process-compose."""
        self.logger.log_info("BMG node shutting down (sidecar lifecycle is external).")

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
            resource_name=f"{self.node_info.node_name}.nest",
        )

    def collect_current_plate_resource(self) -> str:
        """Collect the resource ID of the labware in the BMG plate nest, if any."""
        assay_plate_resource_id = None
        try:
            child_resource = self.resource_client.get_resource(self.plate_carrier).child
            assay_plate_resource_id = (
                child_resource.resource_id if child_resource else None
            )
        except Exception as e:
            self.logger.log_error(e)
        return assay_plate_resource_id

    # ---- State ----------------------------------------------------------------

    def state_handler(self) -> None:
        """Periodically check state of the BMG device via the sidecar."""
        try:
            busy = self._get("is_busy")["busy"]
        except Exception as e:
            self.logger.log_error(f"Error querying sidecar /is_busy: {e}")
            return

        if busy:
            self.node_state = {
                "Temp1 (bottom heating plate)": self.cached_temp1,
                "Temp2 (top heating plate)": self.cached_temp2,
                "Temp3 (optic slide heating plate)": self.cached_temp3,
                "bmg_device_state": "busy",
                "errors": self.cached_current_errors,
            }
            return

        # Device idle — refresh cached values.
        try:
            self.cached_device_state = self._get("status").get("status", "unknown")
        except Exception as e:
            self.logger.log_error(f"Error collecting device state: {e}")

        if self.cached_device_state == "Error":
            self.logger.log_warning("Device is in an Error state.")
            try:
                self.cached_current_errors = self._get("error").get("error")
            except Exception as e:
                self.logger.log_warning(f"Error collecting current device errors: {e}")
        else:
            self.cached_current_errors = None

        try:
            temps = self._get("temps")
            self.cached_temp1 = temps["Temp1"]
            self.cached_temp2 = temps["Temp2"]
            self.cached_temp3 = temps["Temp3"]
            self.node_state = {
                "Temp1 (bottom heating plate)": self.cached_temp1,
                "Temp2 (top heating plate)": self.cached_temp2,
                "Temp3 (optic slide heating plate)": self.cached_temp3,
                "bmg_device_state": self.cached_device_state,
                "errors": self.cached_current_errors,
            }
        except Exception as e:
            self.logger.log_error(f"Error collecting device temperatures: {e}")

    # ---- Actions --------------------------------------------------------------

    @action(name="open")
    def open(self) -> None:
        """Open the BMG plate tray."""
        self.logger.log_info("Opening BMG plate tray.")
        try:
            self._post("plate_out")
        except Exception as e:
            raise Exception(f"Failed to open BMG plate tray: {e}") from e
        self.logger.log_info("BMG plate tray opened.")

    @action(name="close")
    def close(self) -> None:
        """Close the BMG plate tray."""
        self.logger.log_info("Closing BMG plate tray.")
        try:
            self._post("plate_in")
        except Exception as e:
            raise Exception(f"Failed to close BMG plate tray: {e}") from e
        self.logger.log_info("BMG plate tray closed.")

    @action(name="set_temp")
    def set_temp(
        self,
        temp: Annotated[
            float,
            "Temperature in Celsius. Valid options are 0.0, 0.1, or 25.0 through 45.0 (10.0 through 60.0 for extended temperature range models).",
        ],
    ) -> None:
        """Set the temperature on the BMG microplate reader."""
        temp = float(temp)
        min_temp, max_temp = (
            (10.0, 60.0)
            if self.config.extended_temperature_range_model
            else (25.0, 45.0)
        )

        if not (temp in {0.0, 0.1} or min_temp <= temp <= max_temp):
            return ActionFailed(errors=["Invalid temperature input value."])

        try:
            self._post("set_temp", {"temp": temp})
        except requests.HTTPError as e:
            return ActionFailed(errors=[f"Sidecar rejected set_temp: {e}"])
        except Exception as e:
            self.logger.log_error(f"Exception raised from set_temp action: {e}")
            return ActionFailed(errors=[f"Exception raised from set_temp action: {e}"])
        return None

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
        """Run an assay on the BMG plate reader."""
        assay_plate_id = self.collect_current_plate_resource()

        if data_output_directory_path is None:
            data_output_directory_path = str(self.config.data_output_directory_path)
        else:
            try:
                if not Path(data_output_directory_path).is_dir():
                    return ActionFailed(
                        f"data_output_directory_path {data_output_directory_path} is not an existing folder"
                    )
            except Exception as e:
                self.logger.log_error(f"data_directory_output_path is invalid: {e}")
                return ActionFailed(f"data_directory_output_path is invalid: {e}")

        try:
            response = self._post(
                "run_assay",
                {
                    "assay_name": assay_name,
                    "protocol_database_path": str(self.config.db_directory_path),
                    "data_output_directory_path": str(data_output_directory_path),
                    "data_output_file_name": data_output_file_name,
                },
            )
            return (Path(response["data_file_path"]), assay_plate_id)
        except Exception as e:
            self.logger.log_error(f"Error running assay in REST Node. {e}")
            return ActionFailed(errors=[f"Error running assay in REST Node. {e}"])


if __name__ == "__main__":
    bmg_node = BMGNode()
    bmg_node.start_node()
