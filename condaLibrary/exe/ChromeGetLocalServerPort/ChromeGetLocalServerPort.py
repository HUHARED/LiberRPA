# FileName: ChromeGetLocalServerPort.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import sys
import os
import msvcrt

# Set stdin and stdout to binary mode
msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

import json
import struct
from liberrpa.Common._BasicConfig import get_basic_config_dict, get_token
from typing import NoReturn


def send_message(message) -> None:
    encoded_message = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded_message)) + encoded_message)
    sys.stdout.flush()


def main() -> NoReturn:
    while True:
        length = sys.stdin.buffer.read(4)
        if not length:
            sys.exit(0)  # Exit if no input is given
        message_length = struct.unpack("<I", length)[0]

        message_data = sys.stdin.buffer.read(message_length)

        message = json.loads(message_data.decode("utf-8"))
        if message.get("command") == "get_port":
            port: int = int(get_basic_config_dict()["localServerPort"])
            token: str = get_token(clientType="chrome")
            send_message({"port": port, "token": token})


if __name__ == "__main__":
    main()
