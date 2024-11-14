import ctypes
import pythoncom
import comtypes.client

class BmgCom:
   def __init__(self, control_name=None):
       pythoncom.CoInitialize()
       self.com = comtypes.client.CreateObject("BMG_ActiveX.BMGRemoteControl")
       if control_name:
           self.open(control_name)

   def open(self, control_name):
       ep = ctypes.c_char_p(control_name.encode('ascii'))
       res = self.com.OpenConnection(ep)
       if res:
           raise Exception(f"OpenConnection failed: {res}")

   def version(self):
       version = self.com.GetVersion()
       return version

   def dummy(self):
       self.exec('Dummy')

   def status(self):
       item = ctypes.c_char_p(b"Status")
       status = self.com.GetInfo(item)
       return status.strip() if isinstance(status, str) else 'unknown'

   def error(self):
       item = ctypes.c_char_p(b"Error")
       status = self.com.GetInfo(item)
       return status.strip() if isinstance(status, str) else 'unknown'

   def init(self):
       self.exec('Init')

   def plate_in(self):
       self.exec('PlateIn')

   def plate_out(self):
       self.exec('PlateOut')

   def run(self, protocol_name, ):
       self.exec('Run', "RNA", "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit", "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data", 0, 1, 2, "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data", "test2.txt")

   def isBusy(self):
       return self.status() == 'Busy'

   def exec(self, cmd, *args):
       args = tuple((cmd, *args))
       print(args)
       res = self.com.ExecuteAndWait(args)
       if res:
           raise Exception(f"command {cmd} failed: {res}")

if __name__ == '__main__':
   com = BmgCom("CLARIOstar")
   print(f"BMG LABTECH Remote Control Version: {com.version()}")
   com.dummy()
   print(f"Status: {com.status()}")

   # TESTING  command
   #com.plate_out()
   com.plate_in()
   #com.exec("Run", )
   #com.init()
#    print(f"Status: {com.status()}")
#    print(com.run())