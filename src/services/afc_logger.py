import logging
import os

class AFCLogger:
    def __init__(self, log_file='afc.log', log_level=logging.WARNING):
        self.log_file = log_file
        self.log_level = log_level
        self.logger = logging.getLogger('AFCLogger')
        self.logger.setLevel(self.log_level)

        if not self.logger.handlers:
            # File Handler
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(self.log_level)

            # Formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)

            # Add Handler to Logger
            self.logger.addHandler(file_handler)

    def log(self, message, level=logging.INFO):
        if level == logging.DEBUG:
            self.logger.debug(message)
        elif level == logging.INFO:
            self.logger.info(message)
        elif level == logging.WARNING:
            self.logger.warning(message)
        elif level == logging.ERROR:
            self.logger.error(message)
        elif level == logging.CRITICAL:
            self.logger.critical(message)

# Example Usage
if __name__ == '__main__':
    afc_logger = AFCLogger()
    afc_logger.log("This is an info message.")
    afc_logger.log("This is a warning message.", level=logging.WARNING)
    afc_logger.log("This is an error message.", level=logging.ERROR)