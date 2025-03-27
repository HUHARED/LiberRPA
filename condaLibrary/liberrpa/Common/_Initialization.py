# FileName: _Initialization.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import multiprocessing

# run freeze_support() to avoid re-running of it was packaged to an exe.
multiprocessing.freeze_support()

import time
from datetime import datetime
import json
import requests
import os
from pathlib import Path
import platform
import psutil
import socket
import getpass
import subprocess
import ctypes
from screeninfo import get_monitors
from typing import Any

strCwd = os.getcwd()


def _print_program_info() -> None:
    # vscode will cd to the workspace's path.
    print(f"The current workpath: {strCwd}")


def _initialize_project_json() -> None:
    try:
        pathObj = Path("./project.json")
        if pathObj.is_file():
            dictProject = json.loads(pathObj.read_text(encoding="utf-8"))

            # Assign project name no matter it has or not, to make sure the Executor can use the newest project name even user rename the project folder's name.
            dictProject["executorPackageName"] = os.path.basename(strCwd)

            # Logging module need its to name the log folder.
            dictProject["lastStartUpTime"] = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())

        else:
            # Create project.json
            dictProject = {
                "executorPackage": False,
                "executorPackageName": os.path.basename(strCwd),
                "executorPackageVersion": "1.0.0",
                "lastStartUpTime": time.strftime("%Y-%m-%d_%H%M%S", time.localtime()),
            }

        # Save project.json
        pathObj.write_text(
            data=json.dumps(dictProject, indent=4, ensure_ascii=False), encoding="utf-8", errors="strict"
        )

    except Exception as e:
        raise Exception(f"Error to handle project.json: {e}")


def _check_update() -> None:
    # Read local version file.
    try:
        strVersion: str = "None"
        strLiberRPAPath = os.environ.get("LiberRPA")
        if strLiberRPAPath:
            strFile = Path(os.path.join(strLiberRPAPath, "data.json")).read_text(encoding="utf-8")
            strVersion = json.loads(strFile).get("version", "None")
    except Exception as e:
        print(f"Failure to read version data in LiberRPA root folder. {e}")
        return None

    # Try to get version data from GitHub.
    try:
        response = requests.get(
            url="https://raw.githubusercontent.com/HUHARED/LiberRPA/refs/heads/main/data.json",
            timeout=10,
        )
        response.raise_for_status()
        dictTemp = response.json()
        strVersionNewest = dictTemp["version"]
    except Exception as e:
        print(f"Failure to get version data from LiberRPA GitHub repository. {e}")
        return None

    if strVersion != strVersionNewest:
        print(f"LiberRPA can be updated: {strVersion} -> {strVersionNewest}")


def _update_daily_data() -> None:
    """Update some data on the first run of the day, to get some important data, but do not run it every time to save time."""

    strBase = os.path.join(os.environ.get("USERPROFILE", "N/A"), "Documents\\LiberRPA\\")
    strDatePath = os.path.join(strBase, "UpdateDate.txt")
    strSystemDataPath = os.path.join(strBase, "SystemData.json")

    strToday = datetime.strftime(datetime.now(), "%Y-%m-%d")

    # Do update and save date file.
    if not os.path.isfile(strDatePath):
        Path(strSystemDataPath).write_text(
            data=json.dumps(get_system_data(), indent=4, ensure_ascii=False), encoding="utf-8"
        )

        _check_update()

        print(f"Write system information and check update(Only once a day).")

        # Update date file.
        Path(strDatePath).write_text(data=strToday, encoding="utf-8")

        return None

    # Check the date of update. If it's not today, update.
    strDate = Path(strDatePath).read_text(encoding="utf-8")
    if strDate != strToday:
        Path(strSystemDataPath).write_text(
            data=json.dumps(get_system_data(), indent=4, ensure_ascii=False), encoding="utf-8"
        )

        _check_update()

        print(f"Write system information and check update(Only once a day).")

        # Update date file.
        Path(strDatePath).write_text(data=strToday, encoding="utf-8")

        return None
    else:
        # Data is updated today. Do nothing.
        return None


def set_log_folder_name(folderName: str) -> None:
    # Set the name of log folder before first import Log module, call it for making the log folder name more understandable when the Python process works alone.
    os.environ["LogFolderName"] = folderName


def _is_user_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception as e:
        print(f"Error checking admin privileges: {e}")
        return False


def get_system_data() -> dict[str, Any]:
    try:

        dictUserInfo = {
            "Username": getpass.getuser(),
            "Home Directory": os.path.expanduser("~"),
            "Is Admin": "Yes (Admin Privileges)" if _is_user_admin() else "No (No Admin Privileges)",
            "Environment Variables": {
                "User Profile": os.environ.get("USERPROFILE", "N/A"),
                "App Data": os.environ.get("APPDATA", "N/A"),
                "Temp Folder": os.environ.get("TEMP", "N/A"),
                "System Root": os.environ.get("SYSTEMROOT", "N/A"),
            },
            "IP Address": socket.gethostbyname(socket.gethostname()),
        }

        dictSystemInfo = {
            "OS": platform.system(),
            "OS Version": platform.version(),
            "OS Release": platform.release(),
            "Architecture": platform.architecture()[0],
            "Machine": platform.machine(),
            "Processor": platform.processor(),
            "Python Version": platform.python_version(),
            "Python Implementation": platform.python_implementation(),
        }

        listDiskInfo = []

        for partition in psutil.disk_partitions(all=False):
            try:
                # Get the disk usage statistics for the partition
                usage = psutil.disk_usage(partition.mountpoint)

                # Append the partition information to the list
                listDiskInfo.append(
                    {
                        "Device": partition.device,
                        "Mount Point": partition.mountpoint,
                        "File System": partition.fstype,
                        "Total Space (GB)": f"{usage.total / (1024 ** 3):.2f} GB",
                        "Used Space (GB)": f"{usage.used / (1024 ** 3):.2f} GB",
                        "Free Space (GB)": f"{usage.free / (1024 ** 3):.2f} GB",
                        "Percentage Used": f"{usage.percent}%",
                    }
                )
            except PermissionError:
                # If access to a partition is denied, skip it
                print(f"Permission denied for partition: {partition.device}")

            except Exception as e:
                # Append the partition information to the list
                listDiskInfo.append(
                    {
                        "Device": partition.device,
                        "Mount Point": partition.mountpoint,
                        "File System": partition.fstype,
                        "Total Space (GB)": f"Unexpected error retrieving Disk info: {e}",
                        "Used Space (GB)": f"Unexpected error retrieving Disk info: {e}",
                        "Free Space (GB)": f"Unexpected error retrieving Disk info: {e}",
                        "Percentage Used": f"Unexpected error retrieving Disk info: {e}",
                    }
                )

        dictHardwareInfo = {
            "CPU Cores (Logical)": psutil.cpu_count(logical=True),
            "CPU Cores (Physical)": psutil.cpu_count(logical=False),
            "CPU Frequency (MHz)": psutil.cpu_freq().max if psutil.cpu_freq() else "N/A",
            "RAM (Total)": f"{psutil.virtual_memory().total / (1024 ** 3):.2f} GB",
            "RAM (Available)": f"{psutil.virtual_memory().available / (1024 ** 3):.2f} GB",
            "Disk": listDiskInfo,
            "Screen": [str(temp) for temp in get_monitors()],
        }

        try:
            listGpuInfo = (
                subprocess.check_output(
                    "wmic path win32_VideoController get caption,adapterram,driverversion", shell=True
                )
                .decode()
                .strip()
                .split("\n")
            )
            listGpuInfo = [x.strip() for x in listGpuInfo if x.strip()]
        except Exception as e:
            listGpuInfo = f"Error retrieving GPU info: {e}"

        # Collecting network information
        listNetworkInfo = []
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    listNetworkInfo.append(
                        {"Interface": interface, "Address Family": "IPv4", "IP Address": addr.address}
                    )
                elif addr.family == socket.AF_INET6:  # IPv6
                    listNetworkInfo.append(
                        {"Interface": interface, "Address Family": "IPv6", "IP Address": addr.address}
                    )

        dictSystemData = {
            "User Information": dictUserInfo,
            "System Information": dictSystemInfo,
            "Hardware Information": dictHardwareInfo,
            "GPU Information": listGpuInfo,
            "Network Information": listNetworkInfo,
        }

        return dictSystemData

    except Exception as e:
        print(f"Failed to get system data: {e}")
        return {}


if multiprocessing.current_process().name == "MainProcess":
    _print_program_info()
    _initialize_project_json()
    _update_daily_data()

if __name__ == "__main__":
    # _update_daily_data()
    pass
