"""
REST-based node that interfaces with WEI and provides a simple Sleep(t) function
"""

import time
from typing import Annotated
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi.datastructures import UploadFile
from starlette.datastructures import State

# # from typing_extensions import Annotated
from wei.modules.rest_module import RESTModule
from wei.types.module_types import (
    LocalFileModuleActionResult,
    ModuleAction,
    ModuleActionArg,
    ModuleState,
    ModuleStatus,
    ValueModuleActionResult,
)
from wei.types.step_types import (
    ActionRequest,
    StepFileResponse,
    StepResponse,
    StepStatus,
)

from bmg_driver import BmgCom  # import the bmg driver

rest_module = RESTModule(
    name="bmg_module",
    verson="0.0.1",
    description="A REST node to control the BMG VANTAstar microplate reader",
    model="bmg",
)
rest_module.arg_parser.add_argument(
    "--output_path", type=str, help="data ourtput directory path for bmg data", default="C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data"
)

@rest_module.startup()
def bmg_startup(state: State):
    """BMG startup handler"""

    try:
        # Connect to the BMG
        state.bmg = BmgCom("CLARIOstar")

        # TODO: Set module status
        # state.status = check_state(state)
        # print(state.status)
        # QUESTION: Why does state.status[ModuleStatus.READY] = True work for the pf400 but not for my bmg module
        # state.status = state.bmg.status()
        # print(state.status)
        # state.status[ModuleStatus.READY] = True if state.bmg.status() == "Ready" else False
        # print(state.status[ModuleStatus.READY])
        # print(state.bmg.status())

    except Exception:
        print("Something went wrong")
        raise

    else:
        print("BMG online")


# @rest_module.state_handler()
# def check_state(state: State) -> ModuleState:
#     """Updates the BMG state"""

#     bmg_state = state.bmg.status()

#     if bmg_state == "Ready":
#         return ModuleStatus.READY
#     else:
#         return ModuleStatus.ERROR


# OPEN TRAY ACTION 
@rest_module.action(
    name="open", description="Open the bmg plate tray"
)
def open(
    state: State,
    action: ActionRequest,
) -> StepResponse:
    """Opens the BMG plate tray"""
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
    state.bmg.plate_in()
    return StepResponse.step_succeeded()


# RUN ASSAY ACTION
@rest_module.action(
    name="run_assay", description="run an assay on the BMG VANTAstar plate reader"
)
def run_assay(
    state: State,
    action: ActionRequest,
    assay_name: 
) -> StepFileResponse: 
    """Runs an assay on the BMG plate reader"""
    state.bmg.run()


rest_module.start()






