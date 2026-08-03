# FileName: _Structure.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Domain.Repository._Index import get_repository_components_path
from liberrpa.ComponentManagement.Domain.Repository._TransactionStorage import get_repository_staging_path

from pathlib import Path


"""
Component Repository structure:

ComponentRepository/
├── repository.json  # Created after the first successful index write or rebuild.
├── .repository.lock  # Present only while a Repository operation holds the lock.
├── components/
│   ├── ComponentName1_uuidv4/
│   │   ├── componentname1-1.4.2-py313-none-any.whl
│   │   ├── componentname1-1.5.0-py313-none-any.whl
│   │   └── componentname1-2.0.0-py313-none-any.whl
│   └── ComponentName2_uuidv4/
│       └── componentname2-2.3.1-py313-none-any.whl
└── .staging/
    ├── publish_<Transaction UUID>/
    │   ├── transaction.json
    │   └── candidate.whl  # Present only before the Wheel is committed.
    └── import_<Transaction UUID>/
        ├── transaction.json
        └── artifacts/
            ├── 0000/
            │   └── <Original Wheel filename>
            └── 0001/
                └── <Original Wheel filename>
"""


def initialize_repository_structure(repositoryPath: Path) -> tuple[Path, Path]:
    pathComponents = get_repository_components_path(repositoryPath)
    pathStaging = get_repository_staging_path(repositoryPath)

    try:
        pathComponents.mkdir(exist_ok=True)
        pathStaging.mkdir(exist_ok=True)
    except OSError as e:
        raise ComponentManagementError(
            code="repository_unavailable",
            message=f"Failed to initialize the Component Repository structure: {repositoryPath}",
        ) from e

    return pathComponents, pathStaging
