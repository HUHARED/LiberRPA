# FileName: FTP.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import liberrpa.File as File
import ftputil
from pathlib import Path


@Log.trace()
def create_folder(ftpObj: ftputil.FTPHost, folderPath: str) -> None:
    """
    Creates a folder on the FTP server at the specified path.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path where the folder will be created.
    """
    folderPath = folderPath.replace("\\", "/")
    if ftpObj.path.exists(path=folderPath) and ftpObj.path.isdir(path=folderPath):
        raise FileExistsError(f"The folder '{folderPath}' exists.")
    else:
        ftpObj.mkdir(path=folderPath)


@Log.trace()
def get_folder_list(ftpObj: ftputil.FTPHost, folderPath: str) -> list[str]:
    """
    Retrieves a list of folders from the specified path on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path from which to list the folders.

    Returns:
        list[str]: A list of absolute folder paths.
    """
    folderPath = folderPath.replace("\\", "/")
    listFileAndFolder = ftpObj.listdir(folderPath)
    # Generate the absolute paths
    listFileAndFolder = [ftpObj.path.join(folderPath, str(path)) for path in listFileAndFolder]
    listFolder: list[str] = []
    for path in listFileAndFolder:
        if ftpObj.path.isdir(path=path):
            listFolder.append(path)
    return listFolder


@Log.trace()
def get_file_list(ftpObj: ftputil.FTPHost, folderPath: str) -> list[str]:
    """
    Retrieves a list of files from the specified path on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path from which to list the files.

    Returns:
        list[str]: A list of absolute file paths.
    """
    folderPath = folderPath.replace("\\", "/")
    listFileAndFolder = ftpObj.listdir(folderPath)
    # Generate the absolute paths
    listFileAndFolder = [ftpObj.path.join(folderPath, str(path)) for path in listFileAndFolder]
    listFile: list[str] = []
    for path in listFileAndFolder:
        if ftpObj.path.isfile(path=path):
            listFile.append(path)
    return listFile


@Log.trace()
def check_folder_exists(ftpObj: ftputil.FTPHost, folderPath: str) -> bool:
    """
    Checks if a folder exists on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        folderPath: The path to check for existence.

    Returns:
        bool: True if the folder exists, False otherwise.
    """
    folderPath = folderPath.replace("\\", "/")
    return ftpObj.path.exists(path=folderPath) and ftpObj.path.isdir(path=folderPath)


@Log.trace()
def check_file_exists(ftpObj: ftputil.FTPHost, filePath: str) -> bool:
    """
    Checks if a file exists on the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        filePath: The path to check for existence.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    filePath = filePath.replace("\\", "/")
    return ftpObj.path.exists(path=filePath) and ftpObj.path.isfile(path=filePath)


@Log.trace()
def download_file(
    ftpObj: ftputil.FTPHost, remoteFilePath: str, localFilePath: str, overwriteIfExist: bool = False
) -> None:
    """
    Downloads a file from the FTP server to the local machine.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFilePath: The path of the file on the FTP server.
        localFilePath: The path where the file will be saved locally.
        overwriteIfExist: If True, allows overwriting an existing file.
    """
    remoteFilePath = remoteFilePath.replace("\\", "/")
    Path(Path(localFilePath).parent).mkdir(parents=True, exist_ok=True)
    if Path(localFilePath).exists() and Path(localFilePath).is_file() and overwriteIfExist == False:
        raise FileExistsError(f"The file '{localFilePath}' exists.")
    else:
        ftpObj.download(source=remoteFilePath, target=localFilePath)


@Log.trace()
def download_folder(
    ftpObj: ftputil.FTPHost, remoteFolderPath: str, localFolderPath: str, overwriteIfExist: bool = False
) -> None:
    """
    Downloads a folder from the FTP server to the local machine.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFolderPath: The path of the folder on the FTP server.
        localFolderPath: The path where the folder will be saved locally.
        overwriteIfExist: If True, allows overwriting existing files.
    """
    remoteFilePath = remoteFolderPath.replace("\\", "/")
    Path(Path(localFolderPath).parent).mkdir(parents=True, exist_ok=True)
    for path in ftpObj.listdir(remoteFilePath):
        strRemotePath = ftpObj.path.join(remoteFolderPath, str(path))
        strLocalPath = str(Path(localFolderPath).joinpath(str(path)))
        if ftpObj.path.isdir(strRemotePath):
            download_folder(ftpObj=ftpObj, remoteFolderPath=strRemotePath, localFolderPath=strLocalPath)
        else:
            download_file(
                ftpObj=ftpObj,
                remoteFilePath=strRemotePath,
                localFilePath=strLocalPath,
                overwriteIfExist=overwriteIfExist,
            )


@Log.trace()
def upload_file(ftpObj: ftputil.FTPHost, localFilePath: str, remoteFilePath: str) -> None:
    """
    Uploads a file from the local machine to the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        localFilePath: The path of the file on the local machine.
        remoteFilePath: The path where the file will be uploaded on the FTP server.
    """
    remoteFilePath = remoteFilePath.replace("\\", "/")
    if ftpObj.path.isfile(path=remoteFilePath):
        raise FileExistsError(f"The file '{remoteFilePath}' exists.")
    else:
        ftpObj.upload(source=localFilePath, target=remoteFilePath)


@Log.trace()
def upload_folder(ftpObj: ftputil.FTPHost, localFolderPath: str, remoteFolderPath: str) -> None:
    """
    Uploads a local folder and its contents to the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        localFolderPath: The path of the local folder to upload.
        remoteFolderPath: The path on the FTP server where the folder will be uploaded.
    """
    remoteFolderPath = remoteFolderPath.replace("\\", "/")
    localFolderPath = str(Path(localFolderPath).absolute())

    # Create the remote folder if necessary.
    if not (ftpObj.path.exists(path=remoteFolderPath) and ftpObj.path.isdir(path=remoteFolderPath)):
        ftpObj.mkdir(path=remoteFolderPath)

    # Create all folder
    for strFolderPath in File.get_file_or_folder_list(
        folderPath=localFolderPath, filter="folder", getAbsolutePath=True
    ):
        strRelativePath = str(Path(strFolderPath).relative_to(Path(localFolderPath)))
        create_folder(ftpObj=ftpObj, folderPath=ftpObj.path.join(remoteFolderPath, strRelativePath))

    # Upload all files to according folders.
    for strFilePath in File.get_file_or_folder_list(folderPath=localFolderPath, filter="file", getAbsolutePath=True):
        strRelativePath = str(Path(strFilePath).relative_to(Path(localFolderPath)))
        upload_file(
            ftpObj=ftpObj, localFilePath=strFilePath, remoteFilePath=ftpObj.path.join(remoteFolderPath, strRelativePath)
        )


@Log.trace()
def delete_file(ftpObj: ftputil.FTPHost, remoteFilePath: str) -> None:
    """
    Deletes a file from the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFilePath: The path of the file on the FTP server to be deleted.
    """
    remoteFilePath = remoteFilePath.replace("\\", "/")
    if ftpObj.path.isfile(path=remoteFilePath) and ftpObj.path.exists(path=remoteFilePath):
        ftpObj.remove(path=remoteFilePath)
    else:
        raise FileNotFoundError(f"The file '{remoteFilePath}' does not exist.")


@Log.trace()
def delete_folder(ftpObj: ftputil.FTPHost, remoteFolderPath: str) -> None:
    """
    Deletes a folder and its contents from the FTP server.

    Parameters:
        ftpObj: The FTPHost object for making FTP connections.
        remoteFolderPath: The path of the folder on the FTP server to be deleted.
    """
    remoteFolderPath = remoteFolderPath.replace("\\", "/")
    if remoteFolderPath == "/":
        raise ValueError(f"Do not delete the path '{remoteFolderPath}' as it may be the root path of the FTP server.")
    if ftpObj.path.isdir(path=remoteFolderPath) and ftpObj.path.exists(path=remoteFolderPath):
        for path in ftpObj.listdir(path=remoteFolderPath):
            strFullPath = ftpObj.path.join(remoteFolderPath, str(path))
            if ftpObj.path.isdir(path=strFullPath):
                delete_folder(ftpObj=ftpObj, remoteFolderPath=strFullPath)
            else:
                delete_file(ftpObj=ftpObj, remoteFilePath=strFullPath)
        ftpObj.rmdir(path=remoteFolderPath)
    else:
        raise FileNotFoundError(f"The folder '{remoteFolderPath}' does not exist.")


Host = ftputil.FTPHost
""" with FTP.Host(host="", user="", passwd="", encoding="utf-8") as ftpObj: """

if __name__ == "__main__":
    print(Host)
