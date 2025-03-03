# FileName: ChromeGetLocalServerPort.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import sys
import os
import msvcrt

""" strLiberRPAPath = os.environ.get("LiberRPA")
if strLiberRPAPath:
    sys.path.append(os.path.join(strLiberRPAPath, "condaLibrary")) """


# Set stdin and stdout to binary mode
msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

from liberrpa.Common._Initialization import set_log_folder_name

set_log_folder_name(folderName="_ChromeGetLocalServerPort")
from liberrpa.Logging import Log

import json
import struct
from liberrpa.Common._BasicConfig import get_basic_config_dict

Log.info("Get port start.")


@Log.trace()
def send_message(message) -> None:
    encoded_message = json.dumps(message).encode("utf-8")
    Log.debug(f"encoded_message={encoded_message}")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded_message)) + encoded_message)
    sys.stdout.flush()


@Log.trace()
def main():
    while True:
        length = sys.stdin.buffer.read(4)
        Log.debug(f"length={length}")
        if not length:
            Log.critical("No input length received. Exiting.")
            sys.exit(0)  # Exit if no input is given
        message_length = struct.unpack("<I", length)[0]
        Log.debug(f"Expected message length: {message_length}")

        message_data = sys.stdin.buffer.read(message_length)
        Log.debug(f"Received message data: {message_data}")

        message = json.loads(message_data.decode("utf-8"))
        Log.info(f"message={message}")
        if message.get("command") == "get_port":
            port: int = int(get_basic_config_dict()["localServerPort"])
            send_message({"port": port})


if __name__ == "__main__":
    main()
