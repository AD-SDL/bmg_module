"""
REST-based node for BMG microplate readers that interfaces with WEI
"""

from typing import Annotated

from starlette.datastructures import State
from wei.modules.rest_module import RESTModule
from wei.types.step_types import (
    ActionRequest,
    StepFileResponse,
    StepResponse,
    StepStatus,
)

from bmg_interface import BmgCom  # import the bmg interface

rest_module = RESTModule(
    name="bmg_module",
    version="0.0.1",
    description="A REST node to control the BMG VANTAstar microplate reader",
    model="bmg",
)
# add arguments
rest_module.arg_parser.add_argument(
    "--output_path", type=str, help="data output directory path for bmg data", default="C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data"
)
rest_module.arg_parser.add_argument(
    "--db_directory_path", type=str, help="path to directory where assay protocol files are stored", default="C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit"
)
# parse the arguments
args = rest_module.arg_parser.parse_args()


# OPEN TRAY ACTION
@rest_module.action(
    name="open", description="Open the bmg plate tray"
)
def open(
    state: State,
    action: ActionRequest,
) -> StepResponse:
    """Opens the BMG plate tray"""

    state.bmg = BmgCom("CLARIOstar")
    state.bmg.plate_out()
    return StepResponse.step_succeeded()


# CLOSE TRAY ACTION
@rest_module.action(
    name="close", description="Close the BMG plate tray"
)
def close(
    state: State,
    action: ActionRequest,
) -> StepResponse:
    """Closes the BMG plate tray"""

    state.bmg = BmgCom("CLARIOstar")
    state.bmg.plate_in()
    return StepResponse.step_succeeded()


# SET TEMP ACTION
@rest_module.action(
    name="set_temp", description="Set the temperature"
)
def set_temp(
    state: State,
    action: ActionRequest,
    temp: Annotated[float, "temperature in celsius. 00.0 (off), 00.1 (off with temp monitoring), and 25.0-45.0 deg C are valid inputs"]
) -> StepResponse:
    """Sets the temperature on the BMG microplate reader"""

    temp = float(temp)
    if temp in {0.0, 0.1} or 25.0 <= temp <= 45.0:
        # temp input is valid
        state.bmg = BmgCom("CLARIOstar")
        state.bmg.set_temp(temp=temp)
        return StepResponse.step_succeeded()
    else:
        # temp input is not valid
        return StepResponse.step_failed(error="Invalid temperature input value")


# RUN ASSAY ACTION
@rest_module.action(
    name="run_assay", description="run an assay on the BMG VANTAstar plate reader"
)
def run_assay(
    state: State,
    action: ActionRequest,
    assay_name: Annotated[str, "assay to run"],
    data_output_file_name: Annotated[str, "data output file name (ex. data.txt). Will default to <timestamp>.txt (ex. 1731706249.txt) if no file name is entered."] = None,
) -> StepFileResponse:
    """Runs an assay on the BMG plate reader"""

    # run the assay
    state.bmg = BmgCom("CLARIOstar")
    data_file_path = state.bmg.run_assay(
        protocol_name=assay_name,
        protocol_database_path=args.db_directory_path,
        data_output_directory=args.output_path,
        data_output_file_name=data_output_file_name,
        )

    # return the assay results file
    return StepFileResponse(
        StepStatus.SUCCEEDED,
        files={"assay_result": str(data_file_path)}
    )


rest_module.start()






