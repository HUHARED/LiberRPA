# FileName: setup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from setuptools import find_packages, setup

_LONG_DESCRIPTION = """
# liberrpa

`liberrpa` is the core Python library of LiberRPA, an open-source RPA toolchain for Windows.

This PyPI package installs only the Python library. It does not install the full LiberRPA runtime, desktop applications, Chrome extension, local server shortcuts, project templates, FFmpeg, Office-related runtime requirements, or the recommended standard Python environment.

For normal use, install LiberRPA from the official release package and use its documented `default` Python environment.

Advanced users may install `liberrpa` separately, but they are responsible for preparing and maintaining all runtime dependencies required by the LiberRPA modules they use. To ensure that LiberRPA Project editing and execution work as expected, reproduce the dependency set of the official LiberRPA `default` environment according to the project documentation.

Project repository:
https://github.com/HUHARED/LiberRPA
"""


setup(
    name="liberrpa",
    version="0.3.0",
    description="The core Python library of LiberRPA.",
    long_description=_LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Jiyan Hu",
    author_email="mailwork.hu@gmail.com",
    url="https://github.com/HUHARED/LiberRPA",
    project_urls={
        "Source": "https://github.com/HUHARED/LiberRPA",
        "Documentation": "https://github.com/HUHARED/LiberRPA/blob/main/docs/Reference.md",
        "Issue Tracker": "https://github.com/HUHARED/LiberRPA/issues",
    },
    license="AGPL-3.0-or-later",
    license_files=["LICENSE"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
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
    package_data={
        "liberrpa": ["py.typed"],
        "liberrpa.ComponentManagement.Domain.Snippet.Templates": [
            "snippets.jsonc.template"
        ],
    },
    include_package_data=True,
    python_requires=">=3.13,<3.14",
    platforms=["Windows"],
    # Intentionally empty. The PyPI package provides the liberrpa Python library only; the complete runtime dependency set is managed by the official LiberRPA standard Python environment. Users who do not use that environment must install and maintain the required dependencies themselves according to the LiberRPA documentation.
    install_requires=[],
)
