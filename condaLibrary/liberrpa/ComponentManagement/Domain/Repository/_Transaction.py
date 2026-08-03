# FileName: _Transaction.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Domain.Repository._PublishTransaction import recover_publish_transactions
from liberrpa.ComponentManagement.Domain.Repository._ImportTransaction import recover_import_transactions

from pathlib import Path


def recover_repository_transactions(repositoryPath: Path) -> list[DictComponentManagementWarning]:
    return [
        *recover_publish_transactions(repositoryPath),
        *recover_import_transactions(repositoryPath),
    ]
