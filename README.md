# BMG module 

A WEI-powered module for controlling BMG Microplate Readers, currently tested with the VANTAstar model.

Contains a BMG driver (bmg_driver.py) and BMG REST Node (bmg_rest_node.py). 

### Assay Setup on BMG microplate reader

In order to run an assay on the BMG plate reader, you first need to create the assay using the BMG Smart Control software (not the Voyager software). Once the assay is created and saved, it needs to be exported and the .TCS file should be placed inside the BMG directory that contains the assay database .db file ("C:\Program Files (x86)\BMG\CLARIOstar\User\Definit" with default BMG Smart Control on Windows). Once the .TCS file for your assay has been saved into the database directory, it can be accessed by our BMG driver and REST Node by assay name. 

### Running instructions

The BMG driver and REST Node can only connect to the device if run with **32-bit python**. In the following commands, be sure that you're running the correct python version, replacing 'python' with the complete path to your 32-bit python .exe file if necessary. 

#### Installation

When running the last line of these install instructions, be sure to pip install using your 32-bit python. An example of how to do this is below but make sure to replace python.exe with the path to your 32-bit python .exe.

    python.exe -m pip install -e .

General install instructions: 

    git clone https://github.com/AD-SDL/bmg_module.git
    cd bmg_module 
    pip install -e .

If you're having trouble installing the requirements or wei due to an issue installing httptools, use the Visual Studio Installer (download this if you don't have it already), and either modify or install Visual Studio Community 2022 to include "Desktop development with C++".

#### Running the driver

    cd bmg_module
    cd src
    python bmg_driver.py

This will print out the current BMG LABTECH Remote Control Version Number if the driver is able to connect correctly to the BMG device.

You can also use the driver in other programs. See the below python program uses the bmg driver to open and close the plate tray, then sets the temperature and runs an assay named ASSAY_TEST. When connecting, the model must be CLARIOstar even when using a VANTAstar model.

    import bmg_interface

    bmg_device = bmg_interface.BmgCom("CLARIOstar")
    bmg_device.plate_out()
    bmg_device.plate_in()
    bmg_device.set_temp(30.0)
    bmg_device.run_assay(
        protocol_name = "ASSAY_NAME",
        protocol_database_path = "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit" ,
        data_output_directory = "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data",
        data_output_file_name = "assya_data.txt",
    )

Be sure to replace the protocol_database_path and data_output_directory with your correct paths.  


#### Running the REST Node

The REST Node can be started with a command in the format below

    python.exe bmg_rest_node.py --port <your_port> --db_directory_path <(optional) path to bmg db directory containing assay .TCS files> --output_path <(optional) path to directory for saving data output files>


--db_directory_path will default to "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit" unless specified \
and -- output_path will default to "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data" unless specified.

Example usage with no optional arguments (remember to use 32-bit python): 


    python.exe bmg_rest_node.py --port 3003


Example usage with all optional arguments: 


    python.exe bmg_rest_node.py --port 3003 --db_directory_path "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit" --output_path "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data"


### Example Usage in WEI Workflow YAML file

Below is an example of a YAML WEI Workflow file that could interact with the BMG REST Node. 

    name: BMG Example
    author: RPL 
    info: An example WEI workflow to show available BMG actions
    version: '0.1'

    flowdef:
    - name: open bmg
      module: bmg
      action: open

    - name: close bmg
      module: bmg
      action: close

    - name: set temp
      module: bmg
      action: set_temp
      args:
        temp: 30.0

    - name: Run bmg
      module: bmg
      action: run_assay
      args: 
        assay_name: Assay_name
        data_output_file_name: assay_data.txt












