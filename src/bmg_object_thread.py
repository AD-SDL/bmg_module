"""
Object for thread that connects and communicates to the BMG device
"""

import queue
import threading

from madsci.client.event_client import EventClient

from bmg_interface import BmgCom


class BMGThread(threading.Thread):
    """Dedicated thread for BMG communication."""

    def __init__(
        self,
        extended_temperature_range_model: bool,
        logger: EventClient = None,
    ) -> None:
        """Initializes the BMGThread object"""
        super().__init__(daemon=True)

        self.logger = logger or EventClient()
        self.extended_temperature_range_model = extended_temperature_range_model
        self.lock = threading.Lock()

        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.shutdown_event = threading.Event()

        self.bmg = None

    def run(self) -> None:
        """Main thread loop for BMG communication."""
        try:
            # Initialize BMG communication
            self.bmg = BmgCom(
                "CLARIOstar",
                extended_temperature_range_model=self.extended_temperature_range_model,
                logger=self.logger,
            )
            self.logger.log_info("BMG communication thread started.")

            while not self.shutdown_event.is_set():
                try:
                    # Wait for command
                    command = self.command_queue.get(timeout=1)
                    self.logger.log_info(f"Processing command: {command}")

                    # Process command
                    result = self._process_command(command=command)

                    # Send response back
                    self.response_queue.put(result)

                except queue.Empty:
                    # No command received, loop again
                    continue

        except Exception as e:
            self.logger.log_error(f"Error in BMG thread: {e}")
            return

        finally:
            # Clean up BMG communication.
            if self.bmg:
                try:
                    self.bmg.close_connection()
                    self.bmg = None
                    self.logger.log_info("BMG connection closed.")
                except Exception as e:
                    self.logger.log_error(f"Error closing BMG connection: {e}")

    def _process_command(self, command: dict) -> dict:
        """Process a single command and return the result."""
        action = command.get("action")
        result = {"success": False, "data": None, "error": None}

        with self.lock:
            try:
                if action == "plate_out":
                    self.bmg.plate_out()
                    result["success"] = True
                elif action == "plate_in":
                    self.bmg.plate_in()
                    result["success"] = True
                elif action == "set_temp":
                    self._handle_set_temp(command, result)
                elif action == "read_temps":
                    self._handle_read_temps(result)
                elif action == "read_error":
                    self._handle_read_error(result)
                elif action == "device_state":
                    self._handle_device_state(result)
                elif action == "run_assay":
                    self._handle_run_assay(command, result)
                else:
                    result["error"] = f"Unknown action: {action}"

            except Exception as e:
                result["error"] = str(e)
                self.logger.log_error(f"Error processing command {action}: {e}")

        return result

    def _handle_set_temp(self, command: dict, result: dict) -> None:
        """Handle set_temp command."""
        temp = command.get("temp")
        try:
            self.bmg.set_temp(temp=temp)
            result["success"] = True
        except Exception as e:
            result["success"] = False
            result["error"] = e
            raise e

    def _handle_read_temps(self, result: dict) -> None:
        """Handle read_temps command."""
        temps = self.bmg.read_temps()
        if temps:
            result["success"] = True
            result["data"] = temps
        else:
            result["success"] = False
            result["error"] = "Unable to read temperatures from BMG device."

    def _handle_read_error(self, result: dict) -> None:
        """Handle read_temps command."""
        error = self.bmg.get_error()
        if error:
            result["success"] = True
            result["data"] = error
        else:
            result["success"] = False
            result["error"] = "Unable to read error message from BMG device."

    def _handle_device_state(self, result: dict) -> None:
        """Handle device_state command."""
        device_state = self.bmg.get_status()
        result["success"] = True
        result["data"] = device_state

    def _handle_run_assay(self, command: dict, result: dict) -> None:
        """Handle run_assay command."""
        data_filename = None
        data_filename = self.bmg.run_assay(
            assay_name=command.get("protocol_name"),
            protocol_database_path=command.get("protocol_database_path"),
            data_output_directory_path=command.get("data_output_directory_path"),
            data_output_file_name=command.get("data_output_file_name"),
        )
        if data_filename:
            result["success"] = True
            result["data"] = data_filename
        else:
            result["success"] = False
            result["error"] = (
                f"No data_filename returned from _handle_run_assay in bmg_object thread. {data_filename=}"
            )
            self.logger.log_error(
                "No data_filename returned from _handle_run_assay in bmg_object thread"
            )

    def send_command(self, command: dict, timeout: float = 300.0) -> dict:
        """Send a command to the BMG thread and wait for a response.

        Args:
            command (dict): Command to send to the BMG thread.
            timeout (float, optional): Time to wait for a response.

        Returns:
            response (dict): Response from the BMG thread.
        """

        self.command_queue.put(command)
        try:
            return self.response_queue.get(timeout=timeout)
        except queue.Empty:
            self.logger.log_error("Timeout waiting for BMG response.")
            return {
                "success": False,
                "data": None,
                "error": "Timeout waiting for BMG response.",
            }

    def stop(self) -> None:
        """Signal thread to stop and wait for it to finish."""
        # Close connection to the bmg device
        try:
            if self.bmg:
                self.bmg.close_connection()
                self.bmg = None
            else:
                self.logger.log_warning(
                    "No BMG device connection open, unable to close nonexistent connection."
                )
        except Exception:
            self.logger.log_warning("Unable to close connection to bmg device.")

        # Shut down the thread
        self.shutdown_event.set()
        self.join(timeout=5)

        if self.is_alive():
            self.logger.log_warning(
                "BMG communication thread did not terminate in time."
            )
        else:
            self.logger.log_info("BMG communication thread terminated.")

    @property
    def is_busy(self) -> bool:
        """Returns True if the BMG thread is handling a command"""
        return bool(self.lock.locked())
