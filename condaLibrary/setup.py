# FileName: setup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


# For pip editable mode.
from setuptools import setup, find_packages

setup(
    name="liberrpa",
    version="0.2.0",  # Update as appropriate
    description="The main Python module of LiberRPA. If you install it from pip, run the command first: conda install ipykernel pywin32 screeninfo pywinhook pyautogui pyqt pynput keyboard json5 psutil pypdf pathvalidate pillow python-mss flask flask-socketio requests python-socketio websocket-client pyperclip sqlalchemy psycopg2 pymysql pymssql oracledb pandas xlwings ftputil imapclient yagmail ffmpeg",
    author="Jiyan Hu",
    url="https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary/liberrpa",
    license="AGPL-3.0",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Environment :: Win32 (MS Windows)",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
    ],
    packages=find_packages(include=["liberrpa", "liberrpa.*"]),
    include_package_data=True,
    python_requires=">=3.12",
    install_requires=[
        "uiautomation",
        "easyocr",
        "pystray",
        "pyzipper",
        "PyMuPDF",
        "mail-parser",
    ],
)

# pip install uiautomation easyocr pystray pyzipper PyMuPDF mail-parser
