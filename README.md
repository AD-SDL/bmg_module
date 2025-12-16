# BMG Module

A MADSci-powered module for controlling BMG microplate readers, currently tested with the VANTAstar model.

Contains a BMG driver (bmg_driver.py), BMG Object Thread Class (bmg_object_thread.py), and BMG REST Node (bmg_rest_node.py).

### Assay Setup on a BMG Microplate Reader

To run an assay on the BMG plate reader, you must first create the assay using the BMG SMART Control software (not the Voyager software). Once the assay is created and saved, it must be exported, and the .TCS file should be placed inside the BMG directory that contains the assay database .db file ("C:\Program Files (x86)\BMG\CLARIOstar\User\Definit" with default BMG SMART Control on Windows).

Once the .TCS file for your assay has been saved into the database directory, it can be accessed by the BMG driver and REST Node by assay name.

### Running Instructions

The BMG driver and REST Node can only connect to the device when run with **32-bit Python**. When creating your Python virtual environment in the commands below, replace 'python.exe' with the path to a 32-bit Python executable.

#### Installation

Clone the repository:

    git clone https://github.com/AD-SDL/bmg_module.git
    cd bmg_module

Create a virtual environment with 32-bit Python, then activate it. Be sure to use your 32-bit Python path:

    python.exe -m venv .venv
    .venv\Scripts\activate

Install the dependencies using PDM or pip:

    pdm install

or

    pip install -e .

If you're having trouble installing the requirements or MADSci due to an issue installing httptools, use the Visual Studio Installer (download it if you do not already have it), and either modify or install Visual Studio Community 2022 to include Desktop development with C++.

#### Running the interface

Inside the bmg_module directory, run the following commands to test the connection to the BMG device through the BMG interface.

    cd src
    python bmg_interface.py

This will print the current BMG LABTECH Remote Control version number if the driver is able to connect successfully to the BMG device.

You can also use the driver in other programs. The example Python program below uses the BMG driver to open and close the plate tray, set the temperature, and run an assay named ASSAY_NAME.

When instantiating the bmg_device, the model name must be entered as "CLARIOstar" even if you own a BMG VANTAstar device. Also, be sure to replace the protocol_database_path and data_output_directory values with your correct paths.

    import bmg_interface

    bmg_device = bmg_interface.BmgCom("CLARIOstar")
    bmg_device.plate_out()
    bmg_device.plate_in()
    bmg_device.set_temp(30.0)
    bmg_device.run_assay(
        protocol_name = "ASSAY_NAME",
        protocol_database_path = "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit" ,
        data_output_directory = "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data",
        data_output_file_name = "assay_data.txt",
    )


#### Running the REST Node

The REST Node can be started with a command in the format below.

    python bmg_rest_node.py --node_url <(str, optional) address for your LiCONiC MADSci REST Node> --db_directory_path <(str, optional) path to bmg db directory containing assay .TCS files> --output_path <(str, optional) path to directory for saving data output files>

--node_url will default to "http://127.0.0.1:2000" \
--db_directory_path will default to "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit" \
and -- output_path will default to "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data"

Example usage with no optional arguments:


    python bmg_rest_node.py


Example usage with all optional arguments:


    python bmg_rest_node.py --node_url "http://127.0.0.1:3003" --db_directory_path "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit" --output_path "C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Data"


### Example Usage in MADSci Workflow YAML file

Below is an example of a MADSci YAML workflow file that interacts with the BMG REST Node. Replace "ASSAY_NAME" and "ASSAY_DATA.txt" with the name of the assay you wish to run on the BMG and the desired output data file name.

    name: Test Workflow

    metadata:
        author: Casey Stone
        info: Example MADSci workflow for BMG actions
        version: 0.1

    steps:
    - name: open BMG
      node: bmg
      action: open

    - name: close bmg
      node: bmg
      action: close

    - name: set temp
      node: bmg
      action: set_temp
      args:
        temp: 30.0

    - name: Run bmg
      node: bmg
      action: run_assay
      args:
        assay_name: ASSAY_NAME
        data_output_file_name: ASSAY_DATA.txt
