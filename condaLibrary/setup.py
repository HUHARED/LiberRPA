# FileName: setup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


# For pip editable mode.
from setuptools import setup, find_packages

_LONG_DESCRIPTION = """
# liberrpa

`liberrpa` is the core Python library of LiberRPA, an open-source RPA toolchain for Windows.

This PyPI package only installs the Python library. It does not install the full LiberRPA runtime, desktop applications, Chrome extension, local server shortcuts, project templates, FFmpeg, Office-related runtime requirements, or the recommended standard Python environment.

For normal users, please install LiberRPA from the official release package and use the bundled or documented standard Python environment.

Advanced users may install this package manually, but they are responsible for preparing all required runtime dependencies.
"""

setup(
    name="liberrpa",
    version="0.2.0",  # Update as appropriate
    description="The main Python library of LiberRPA.",
    long_description=_LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Jiyan Hu",
    author_email="mailwork.hu@gmail.com",
    url="https://github.com/HUHARED/LiberRPA",
    project_urls={
        "Source": "https://github.com/HUHARED/LiberRPA",
        "Documentation": "https://github.com/HUHARED/LiberRPA",
        "Issue Tracker": "https://github.com/HUHARED/LiberRPA/issues",
    },
    license="AGPL-3.0-or-later",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords=[
        "rpa",
        "automation",
        "windows",
        "desktop-automation",
        "browser-automation",
    ],
    packages=find_packages(include=["liberrpa", "liberrpa.*"]),
    include_package_data=True,
    python_requires=">=3.12,<3.13",
    platforms=["Windows"],
    install_requires=[
        # Keep this list intentionally small.
        #
        # The complete LiberRPA runtime dependencies are managed by the official
        # LiberRPA standard environment. Do not use install_requires as a full
        # replacement for that environment.
        "uiautomation",
        # "easyocr",
        # "pystray",
        "pyzipper",
        "PyMuPDF",
        "mail-parser",
    ],
)
