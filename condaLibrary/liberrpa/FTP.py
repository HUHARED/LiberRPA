# FileName: FTP.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import StrPath
import liberrpa.File as File

import ftputil
from pathlib import Path
import os


def _to_ftp_path(path: StrPath) -> str:
    """Convert a StrPath to an FTP-style path."""
    return os.fspath(path).replace("\\", "/")


@Log.trace()
def create_folder(ftpObj: ftputil.FTPHost, folderPath: StrPath) -> None:
    """
    Creates a folder on the FTP server at the specified path.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path where the folder will be created.
    """
    folderPath = _to_ftp_path(folderPath)
    if ftpObj.path.exists(path=folderPath) and ftpObj.path.isdir(path=folderPath):
        raise FileExistsError(f"The folder '{folderPath}' exists.")
    else:
        ftpObj.mkdir(path=folderPath)


@Log.trace()
def get_folder_list(ftpObj: ftputil.FTPHost, folderPath: StrPath) -> list[str]:
    """
    Retrieves a list of folders from the specified path on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path from which to list the folders.

    Returns:
        list[str]: A list of absolute folder paths.
    """
    folderPath = _to_ftp_path(folderPath)

    # Generate the absolute paths
    listFileAndFolder = [ftpObj.path.join(folderPath, os.fsdecode(path)) for path in ftpObj.listdir(folderPath)]

    listFolder: list[str] = []
    for path in listFileAndFolder:
        if ftpObj.path.isdir(path=path):
            listFolder.append(path)
    return listFolder


@Log.trace()
def get_file_list(ftpObj: ftputil.FTPHost, folderPath: StrPath) -> list[str]:
    """
    Retrieves a list of files from the specified path on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path from which to list the files.

    Returns:
        list[str]: A list of absolute file paths.
    """
    folderPath = _to_ftp_path(folderPath)

    # Generate the absolute paths
    listFileAndFolder = [ftpObj.path.join(folderPath, os.fsdecode(path)) for path in ftpObj.listdir(folderPath)]

    listFile: list[str] = []
    for path in listFileAndFolder:
        if ftpObj.path.isfile(path=path):
            listFile.append(path)
    return listFile


@Log.trace()
def check_folder_exists(ftpObj: ftputil.FTPHost, folderPath: StrPath) -> bool:
    """
    Checks if a folder exists on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path to check for existence.

    Returns:
        bool: True if the folder exists, False otherwise.
    """
    folderPath = _to_ftp_path(folderPath)
    return ftpObj.path.exists(path=folderPath) and ftpObj.path.isdir(path=folderPath)


@Log.trace()
def check_file_exists(ftpObj: ftputil.FTPHost, filePath: StrPath) -> bool:
    """
    Checks if a file exists on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        filePath: The path to check for existence.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    filePath = _to_ftp_path(filePath)
    return ftpObj.path.exists(path=filePath) and ftpObj.path.isfile(path=filePath)


@Log.trace()
def download_file(
    ftpObj: ftputil.FTPHost,
    remoteFilePath: StrPath,
    localFilePath: StrPath,
    overwrite: bool = False,
) -> None:
    """
    Downloads a file from the FTP server to the local machine.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFilePath: The path of the file on the FTP server.
        localFilePath: The path where the file will be saved locally.
        overwrite: If True, allows overwriting an existing file.
    """
    remoteFilePath = _to_ftp_path(remoteFilePath)
    localFilePath = Path(localFilePath)

    localFilePath.parent.mkdir(parents=True, exist_ok=True)

    if localFilePath.exists() and localFilePath.is_file() and not overwrite:
        raise FileExistsError(f"The file '{localFilePath}' exists.")
    else:
        ftpObj.download(source=remoteFilePath, target=os.fspath(localFilePath))


@Log.trace()
def download_folder(
    ftpObj: ftputil.FTPHost,
    remoteFolderPath: StrPath,
    localFolderPath: StrPath,
    overwrite: bool = False,
) -> None:
    """
    Downloads a folder from the FTP server to the local machine.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFolderPath: The path of the folder on the FTP server.
        localFolderPath: The path where the folder will be saved locally.
        overwrite: If True, allows overwriting existing files.
    """

    remoteFolderPath = _to_ftp_path(remoteFolderPath)
    localFolderPath = Path(localFolderPath)

    localFolderPath.mkdir(parents=True, exist_ok=True)

    for path in ftpObj.listdir(remoteFolderPath):
        fileName = os.fsdecode(path)

        remotePath = ftpObj.path.join(remoteFolderPath, fileName)
        localPath = localFolderPath / fileName

        if ftpObj.path.isdir(path=remotePath):
            download_folder(
                ftpObj=ftpObj,
                remoteFolderPath=remotePath,
                localFolderPath=localPath,
                overwrite=overwrite,
            )
        else:
            download_file(
                ftpObj=ftpObj,
                remoteFilePath=remotePath,
                localFilePath=localPath,
                overwrite=overwrite,
            )


@Log.trace()
def upload_file(ftpObj: ftputil.FTPHost, localFilePath: StrPath, remoteFilePath: StrPath) -> None:
    """
    Uploads a file from the local machine to the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        localFilePath: The path of the file on the local machine.
        remoteFilePath: The path where the file will be uploaded on the FTP server.
    """
    remoteFilePath = _to_ftp_path(remoteFilePath)

    if ftpObj.path.isfile(path=remoteFilePath):
        raise FileExistsError(f"The file '{remoteFilePath}' exists.")
    else:
        ftpObj.upload(source=os.fspath(localFilePath), target=remoteFilePath)


@Log.trace()
def upload_folder(ftpObj: ftputil.FTPHost, localFolderPath: StrPath, remoteFolderPath: StrPath) -> None:
    """
    Uploads a local folder and its contents to the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        localFolderPath: The path of the local folder to upload.
        remoteFolderPath: The path on the FTP server where the folder will be uploaded.
    """

    remoteFolderPath = _to_ftp_path(remoteFolderPath)
    localFolderPath = Path(localFolderPath).absolute()

    # Create the remote folder if necessary.
    if not (ftpObj.path.exists(path=remoteFolderPath) and ftpObj.path.isdir(path=remoteFolderPath)):
        ftpObj.mkdir(path=remoteFolderPath)

    # Create all folders.
    for folderPath in File.get_file_or_folder_list(
        folderPath=localFolderPath,
        itemType="folder",
        getAbsolutePath=True,
    ):
        relativePath = Path(folderPath).relative_to(localFolderPath).as_posix()
        create_folder(ftpObj=ftpObj, folderPath=ftpObj.path.join(remoteFolderPath, relativePath))

    # Upload all files to according folders.
    for filePath in File.get_file_or_folder_list(
        folderPath=localFolderPath,
        itemType="file",
        getAbsolutePath=True,
    ):
        relativePath = Path(filePath).relative_to(localFolderPath).as_posix()
        upload_file(
            ftpObj=ftpObj,
            localFilePath=filePath,
            remoteFilePath=ftpObj.path.join(remoteFolderPath, relativePath),
        )


@Log.trace()
def delete_file(ftpObj: ftputil.FTPHost, remoteFilePath: StrPath) -> None:
    """
    Deletes a file from the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFilePath: The path of the file on the FTP server to be deleted.
    """
    remoteFilePath = _to_ftp_path(remoteFilePath)
    if ftpObj.path.exists(path=remoteFilePath) and ftpObj.path.isfile(path=remoteFilePath):
        ftpObj.remove(path=remoteFilePath)
    else:
        raise FileNotFoundError(f"The file '{remoteFilePath}' does not exist.")


@Log.trace()
def delete_folder(ftpObj: ftputil.FTPHost, remoteFolderPath: StrPath) -> None:
    """
    Deletes a folder and its contents from the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFolderPath: The path of the folder on the FTP server to be deleted.
    """
    remoteFolderPath = _to_ftp_path(remoteFolderPath)

    if remoteFolderPath == "/":
        raise ValueError(f"Do not delete the path '{remoteFolderPath}' as it may be the root path of the FTP server.")

    if ftpObj.path.exists(path=remoteFolderPath) and ftpObj.path.isdir(path=remoteFolderPath):
        for path in ftpObj.listdir(path=remoteFolderPath):
            fileName = os.fsdecode(path)
            fullPath = ftpObj.path.join(remoteFolderPath, fileName)

            if ftpObj.path.isdir(path=fullPath):
                delete_folder(ftpObj=ftpObj, remoteFolderPath=fullPath)
            else:
                delete_file(ftpObj=ftpObj, remoteFilePath=fullPath)

        ftpObj.rmdir(path=remoteFolderPath)
    else:
        raise FileNotFoundError(f"The folder '{remoteFolderPath}' does not exist.")


Host = ftputil.FTPHost
""" with FTP.Host(host="", user="", passwd="", encoding="utf-8") as ftpObj: """

if __name__ == "__main__":
    print(Host)
