"""
Driver for the BMG microplate reader (our model is VANTAstar)
"""

import ctypes

import comtypes.client
import pythoncom


class BmgCom:
    def __init__(self, control_name=None):
        """Initializes and opens the connection the BMG plate reader"""
        pythoncom.CoInitialize()
        self.com = comtypes.client.CreateObject("BMG_ActiveX.BMGRemoteControl")
        if control_name:
            self.open_connection(control_name)

    def open_connection(self, control_name):
        """Open a connection to the BMG plate reader"""
        ep = ctypes.c_char_p(control_name.encode('ascii'))
        res = self.com.OpenConnection(ep)
        if res:
            raise Exception(f"OpenConnection failed: {res}")

    def close_connection(self):
        """Close the connection to the BMG plate reader"""
        res = self.com.CloseConnection()
        if res:
            raise Exception(f"CloseConnection failed: {res}")

    def version(self):
        """Returns the BMG instrument version"""
        version = self.com.GetVersion()
        return version

    def dummy(self):
        """Use this to test if a connection to a BMG plate reader is active"""
        self.exec('Dummy')

    def status(self):
        """Returns the current status of the BMG plate reader"""
        item = ctypes.c_char_p(b"Status")
        status = self.com.GetInfo(item)
        return status.strip() if isinstance(status, str) else 'unknown'

    def error(self):
        """Returns any errors on the BMG plate reader"""
        item = ctypes.c_char_p(b"Error")
        status = self.com.GetInfo(item)
        return status.strip() if isinstance(status, str) else 'unknown'

    def init(self):
        """Initializes the BMG plate reader"""
        self.exec('Init')

    def plate_in(self):
        """Closes the plate tray on the BMG plate reader"""
        self.exec('PlateIn')

    def plate_out(self):
        """Opens the plate tray on the BMG plate reader"""
        self.exec('PlateOut')

    def run_assay(
        self,
        protocol_name:str,
        protocol_database_path:str,
        data_output_directory:str,
        data_output_filename:str,
        plate_id1:int = 1,  # these plate IDs are optional
        plate_id2:int = 2,  # but why? what do they do?
        plate_id3:int = 3,  # and why are there three? curious.

    ):
        """Runs an assay on the BMG plate reader"""
        self.exec(
            'Run',
            protocol_name,
            protocol_database_path,
            data_output_directory,
            plate_id1,
            plate_id2,
            plate_id3,
            data_output_directory,
            data_output_filename
        )

    def isBusy(self):
        """Returns True if BMG is busy, False if not busy"""
        return self.status() == 'Busy'

    def exec(self, cmd, *args):
        """Executed a command over the established connection with the BMG plate reader"""
        args = tuple((cmd, *args))
        print(args)
        res = self.com.ExecuteAndWait(args)
        if res:
            raise Exception(f"command {cmd} failed: {res}")

if __name__ == '__main__':
   com = BmgCom("CLARIOstar")
   print(f"BMG LABTECH Remote Control Version: {com.version()}")





