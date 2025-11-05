import threading
import queue

from bmg_interface import BmgCom

class BMGThread(threading.Thread):
    """Dedicated thread for BMG communication."""

    def __init__(self, resource_client, plate_carrier, logger):
        super().__init__(daemon=True)
        self.resource_client = resource_client
        self.plate_carrier = plate_carrier
        self.logger = logger
        self.lock = threading.Lock()

        # communication queue 
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.shutdown_event = threading.Event()

        self.bmg = None

    def run(self):
        """Main thread loop for BMG communication."""
        try: 
            # initialize BMG communication
            self.bmg = BmgCom(
                "CLARIOstar",
                resource_client=self.resource_client,
                plate_carrier=self.plate_carrier,
                logger=self.logger,
            )
            self.logger.log_info("BMG communication thread started.")

            while not self.shutdown_event.is_set():
                # self.logger.log_info("Waiting for command...")  # TESTING
                try:
                    command = self.command_queue.get(timeout=1)  # wait for command
                    self.logger.log_info(f"Processing command: {command}")

                    # process command
                    action = command.get("action")
                
                    # TESTING
                    self.logger.log_info(f"ACTION FOUND IN THREAD RUN FUNCTION: {action}")
                    result = {
                        "success": False, 
                        "data": None, 
                        "error": None
                    }

                    with self.lock:
                        try: 
                            if action == "plate_out":
                                self.bmg.plate_out()
                                result["success"] = True
                            elif action == "plate_in":
                                self.bmg.plate_in()
                                result["success"] = True
                            elif action == "set_temp":
                                temp = command.get("temp")
                                self.bmg.set_temp(temp=temp)
                                result["success"] = True
                            elif action == "read_temps":
                                temps = self.bmg.read_temps()
                                result["success"] = True
                                result["data"] = temps
                            elif action == "run_assay": 
                                data_filename = self.bmg.run_assay(
                                    protocol_name=command.get("protocol_name"),
                                    protocol_database_path=command.get("protocol_database_path"),
                                    data_output_directory=command.get("data_output_directory"),
                                    data_output_file_name=command.get("data_output_file_name"),
                                )
                                if data_filename:
                                    result["data"] = data_filename

                                # TODO: do we want to fail the action if no filename is returned?
                                # presumably there's a backup on the windows machine if this happens
                                result["success"] = True 
                            
                            else:
                                result["error"] = f"Unknown action: {action}"

                        except Exception as e:
                            result["error"] = str(e)
                            self.logger.log_error(f"Error processing command {action}: {e}")

                    # Send response back
                    self.response_queue.put(result)

                except queue.Empty:
                    continue  # no command received, loop again


        except Exception as e:
            self.logger.log_error(f"Error in BMG thread: {e}")
            return   # TODO: should I be returning here? - kills the thread if there's an error during init?
        
        finally: 
            # clean up BMG communication
            if self.bmg:
                try:
                    self.bmg.close_connection()
                    self.bmg = None
                    self.logger.log_info("BMG connection closed.")
                except Exception as e:
                    self.logger.log_error(f"Error closing BMG connection: {e}")

    def send_command(self, command: dict, timeout: float = 300.0) -> dict:
        """Send a command to the BMG thread and wait for a response.

        TODO: how long should the timeout be?

        Args:
            command (dict): Command to send to the BMG thread.
            timeout (float): Time to wait for a response.

        Returns:
            dict: Response from the BMG thread.
        
        """
        # TESTING
        self.logger.log_info(f"COMMAND IN THREAD SEND COMMAND FUNCTION: {command}")

        self.command_queue.put(command)
        try:
            response = self.response_queue.get(timeout=timeout)
            return response
        except queue.Empty:
            self.logger.log_error("Timeout waiting for BMG response.")
            return {"success": False, "data": None, "error": "Timeout waiting for BMG response."}
    
    
    def stop(self):
        """Signal thread to stop and wait for it to finish."""
        self.shutdown_event.set()
        self.join(timeout=5)

        if self.is_alive():
            self.logger.log_warning("BMG communication thread did not terminate in time.")
        else:   
            self.logger.log_info("BMG communication thread terminated.")

    @property
    def is_busy(self) -> bool:
        """Returns True if the BMG thread is handling a command"""
        return bool(self.lock.locked())
    
        