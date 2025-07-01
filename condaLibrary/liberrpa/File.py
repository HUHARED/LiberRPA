# FileName: File.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import Encoding
from pathlib import Path
import shutil
import fnmatch
import pyzipper
import configparser
from pypdf import PdfReader, PdfWriter
import fitz  # PyMuPDF
import os
import io
from PIL import Image
from typing import Literal, Any
import pandas
import time


@Log.trace()
def create_folder(folderPath: str, createParent: bool = True, errorIfExisted: bool = False) -> None:
    """
    Creates a folder at the specified path.

    Parameters:
        folderPath: The path where the folder will be created.
        createParent: If True, creates all missing parent directories. If False, an error is raised if a parent directory is missing.
        errorIfExisted: If True, raises an error if the folder already exists; otherwise, does nothing if the folder exists.
    """
    Path(folderPath).mkdir(parents=createParent, exist_ok=not errorIfExisted)


@Log.trace()
def read_file_content(filePath: str, encoding: Encoding = "utf-8") -> str:
    """
    Reads the content of a file using the specified encoding.

    Parameters:
        filePath: The path of the file to read.
        encoding: The encoding to use for reading the file. If None, uses the system default.

    Returns:
        str: The content of the file as a string.
    """
    return Path(filePath).read_text(encoding=encoding, errors="strict")


@Log.trace()
def write_file(
    filePath: str,
    text: str,
    encoding: Encoding = "utf-8",
) -> None:
    """
    Overwrites the content of a specified file with the given text, using the specified encoding.
    A new file will be created if "filePath" doesn't exist.

    Parameters:
        filePath: The path of the file whose content is to be overwritten.
        text: The text to write into the file.
        encoding: The encoding to use for writing the text to the file. Defaults to "utf-8".
    """

    Path(filePath).write_text(data=text, encoding=encoding, errors="strict")


@Log.trace()
def append_write_file(filePath: str, text: str, encoding: Encoding = "utf-8") -> None:
    """
    Appends text to the end of a specified file without overwriting its existing content, using the specified encoding.
    A new file will be created if "filePath" doesn't exist.

    Parameters:
        filePath: The path of the file to which the text is to be appended.
        text: The text to append to the file.
        encoding: The encoding to use for writing the text to the file. Defaults to "utf-8".
    """
    with Path(filePath).open(mode="a", encoding=encoding, errors="strict", newline=None) as fileObj:
        fileObj.write(text)


@Log.trace()
def wait_file_download(filePath: str, retryTimes: int = 10, retryInterval: int = 1, threshold: int = 1) -> None:
    """
    Waits for a file to finish downloading by checking its size. It will throw a TimeoutError If the file does not reach the expected size within the given attempts.

    Parameters:
    - filePath: The path of the file to check.
    - retryTimes: The number of times to check before timing out.
    - retryInterval: The time(in seconds) to wait between retries.
    - threshold: The minimum file size(in bytes) to consider the download complete.
    """
    for idx in range(0, retryTimes, 1):
        # If Path(filePath).stat() is called on a non-existent file, it will raise a FileNotFoundError.

        # Sometimes, the file may not be created.
        if not Path(filePath).exists():
            Log.debug(f"Not found file in the path: {filePath}")
            time.sleep(retryInterval)
            continue

        intFileSize = Path(filePath).stat().st_size
        if intFileSize < threshold:
            Log.debug(f"Current file size is {intFileSize} bytes.")
            time.sleep(retryInterval)
            continue
        else:
            return None
    raise TimeoutError(f"The file {filePath} didn't download completed.")


@Log.trace()
def get_file_fullname(filePath: str) -> str:
    """
    Get the final path component(basename and suffix).

    Parameters:
        filePath: The filePath path.

    Returns:
        str: The file's name
    """
    return Path(filePath).name


@Log.trace()
def get_file_basename(filePath: str) -> str:
    """
    Get the final path component, minus its last suffix.

    Parameters:
        filePath: The filePath path.

    Returns:
        str: The file's basename(without suffix)
    """
    return Path(filePath).stem


@Log.trace()
def get_file_suffix(filePath: str) -> str:
    """
    Get the file's suffix(contains the dot).

    Parameters:
        filePath: The filePath path.

    Returns:
        str: The file's suffix(contains the dot)
    """
    return Path(filePath).suffix


@Log.trace()
def check_file_exists(filePath: str) -> bool:
    """
    Whether this path is a regular file (also True for symlinks pointing to regular files).

    Parameters:
        filePath: The path of the folder to check.

    Returns:
        bool: If the path is not exists, it will return False.
    """
    return Path(filePath).is_file()


@Log.trace()
def check_folder_exists(folderPath: str) -> bool:
    """
    Whether this path is a directory.

    Parameters:
        folderPath: The path of the folder to check.

    Returns:
        bool: If the path is not exists, it will return False.
    """
    return Path(folderPath).is_dir()


@Log.trace()
def get_parent_folder_path(path: str) -> str:
    """
    Returns the absolute path of the parent folder for a given path.

    Parameters:
        path: The path for which to retrieve the parent directory.

    Returns:
        str: The absolute path of the parent folder.
    """
    return str(Path(path).parent.resolve())


@Log.trace()
def get_file_size(filePath: str) -> int:
    """
    Returns the size of the specified file in bytes.

    Parameters:
        filePath: The path to the file whose size is to be determined.

    Returns:
        int: The size of the file in bytes.
    """
    return Path(filePath).stat().st_size


@Log.trace()
def get_folder_size(folderPath: str) -> int:
    """
    Calculates the total size of all files within the specified folder and its subfolders.

    Parameters:
        folderPath: The path of the folder for which the total file size is to be calculated.

    Returns:
        int: The total size of all files in the specified folder, measured in bytes.
    """
    intTotalSize = 0
    for item in Path(folderPath).rglob("*"):  # rglob('*') iterates over all files and directories within
        if item.is_file():
            intTotalSize += item.stat().st_size
    return intTotalSize


@Log.trace()
def copy_file(srcFilePath: str, dstFilePath: str, overwriteIfExist: bool = False) -> str:
    """
    Copies a file from a source path to a destination path and returns the absolute path of the destination file.

    Optionally allows overwriting of an existing file at the destination.

    Parameters:
        srcFilePath: The path of the source file to copy.
        dstFilePath: The path where the source file should be copied to.
        overwriteIfExist: If set to True, the destination file will be overwritten if it already exists;

            if False, a FileExistsError will be raised if the destination file exists.

    Returns:
        str: The absolute path of the copied file at the destination.
    """
    if overwriteIfExist == False and Path(dstFilePath).is_file():
        raise FileExistsError(f"There is a file in the destination path: {Path(dstFilePath).resolve()}")

    return str(Path(shutil.copyfile(src=srcFilePath, dst=dstFilePath)).resolve())


@Log.trace()
def copy_folder(srcFolderPath: str, dstFolderPath: str) -> str:
    """
    Recursively copy a directory tree. The destination directory must not already exist.

    Parameters:
        srcFolderPath: The path of the source folder to copy.
        dstFolderPath: The path where the source folder should be copied to. This path must not already exist.

    Returns:
        str: The absolute path of the destination folder after copying.
    """
    Path(dstFolderPath).mkdir(parents=True, exist_ok=False)

    return str(Path(shutil.copytree(src=srcFolderPath, dst=dstFolderPath)).resolve())


@Log.trace()
def move_file_or_folder(srcPath: str, dstPath: str) -> str:
    """
    Recursively move a file or directory to another location. This is similar to the Unix "mv".

    Return the file or directory's destination. It will overwrite the destination file by default if it exists.

    Parameters:
        srcPath: The path of the file or folder to move.
        dstPath: The path where the file or folder should be moved to.

    Returns:
        str: The absolute path of the dstPath.
    """
    return str(Path(shutil.move(src=srcPath, dst=dstPath)).resolve())


@Log.trace()
def remove_file(filePath: str) -> None:
    Path(filePath).unlink()


@Log.trace()
def remove_folder(folderPath: str) -> None:
    shutil.rmtree(path=folderPath)


@Log.trace()
def get_file_or_folder_list(
    folderPath: str,
    filter: Literal["file", "folder", "both"] = "both",
    getAbsolutePath: bool = True,
    ignorePrefixes: list[str] = [],
    ignoreSuffixes: list[str] = [],
) -> list[str]:
    """
    Retrieves a list of files or folders from a specified directory based on a filter.

    Parameters:
        folderPath: The directory path from which to list files or folders.
        filter: Specifies the type of items to list; "file" for files only, "folder" for folders only, or "both" for all items.
        getAbsolutePath: If True, returns absolute paths; if False, returns only the names.
        ignorePrefixes: A list of path prefixes to ignore. Any item starting with one of these prefixes won't be included in the result.
        ignoreSuffixes: A list of path suffixes to ignore. Any item ending with one of these prefixes won't be included in the result.

    Returns:
        list[str]: A list of file or folder paths or names, depending on `getAbsolutePath`, filtered as specified.
    """
    pathObj = Path(folderPath).resolve()
    # print(pathObj)
    if not pathObj.is_dir():
        raise ValueError(f"Provided path({folderPath}) is not a folder")

    listValue = ["file", "folder", "both"]
    if filter not in listValue:
        raise ValueError(f"The argument filter should be one of {listValue}")

    paths = pathObj.rglob("*")

    listResult: list[Path] = []

    for path in paths:
        if any(str(path).startswith(str(Path(folderPath).resolve().joinpath(prefix))) for prefix in ignorePrefixes):
            continue
        if any(str(path).endswith(suffix) for suffix in ignoreSuffixes):
            continue

        if filter == "file" and path.is_file():
            listResult.append(path)
        elif filter == "folder" and path.is_dir():
            listResult.append(path)
        elif filter == "both":
            listResult.append(path)

    if getAbsolutePath:
        return [str(p.resolve()) for p in listResult]
    else:
        return [str(p.relative_to(pathObj)) for p in listResult]


@Log.trace()
def search_file_or_folder(folderPath: str, name: str, deepIterate=True) -> list[str]:
    """
    Searches for files or folders within a given directory based on a name or pattern.

    Parameters:
        folderPath: The directory path within which to search.
        name: The name or wildcard pattern to match against file or folder names. Patterns are Unix shell style:
        * matches everything
        ? matches any single character
        [seq] matches any character in seq
        [!seq] matches any char not in seq
        deepIterate: If True, searches recursively through all subdirectories; if False, searches only in the specified directory.

    Returns:
        list[str]: A list of paths to the files or folders that match the specified name or pattern.
    """
    if not Path(folderPath).exists():
        raise FileNotFoundError("File/Folder does not exist.")
    if not Path(folderPath).is_dir():
        raise FileNotFoundError("Invalid folder path.")

    listRetPath = []

    pathObj = Path(folderPath).resolve()
    if deepIterate:
        for item in pathObj.rglob("*"):
            if fnmatch.fnmatch(item.name, name):
                listRetPath.append(str(item))
    else:
        for item in pathObj.glob(name):
            listRetPath.append(str(item))

    return listRetPath


@Log.trace()
def zip_create(srcPath: str, dstPath: str, password: str = "") -> str:
    """
    Create a ZIP file from a file or folder, with optional password protection.

    Parameters:
        srcPath: Path to the file or folder to be zipped.
        dstPath: Path where the ZIP file will be saved.
        password: Password for the ZIP file, If it's empty string, means have no password.

    Returns:
        str: The absolute path to the created ZIP file.
    """

    srcPathObj = Path(srcPath)
    dstPathObj = Path(dstPath)
    if dstPathObj.is_dir():
        dstPathObj = dstPathObj / (srcPathObj.name + ".zip")
    # print(destinationPathObj)

    encryption_method = pyzipper.WZ_AES if password else None

    with pyzipper.AESZipFile(
        str(dstPathObj),
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=encryption_method,
    ) as zipFile:
        if password:
            zipFile.setpassword(password.encode())
        if srcPathObj.is_file():
            zipFile.write(srcPathObj, srcPathObj.name)
        elif srcPathObj.is_dir():
            for file in srcPathObj.rglob("*"):
                zipFile.write(file, file.relative_to(srcPathObj))

    return str(dstPathObj.resolve())


@Log.trace()
def zip_extract(zipPath: str, dstFolderPath: str, password: str = "") -> str:
    """
    Extract a ZIP file, with optional password protection.

    Parameters:
        zipPath: Path to the ZIP file.
        dstFolderPath: Path where the contents will be extracted.
        password: Password for the ZIP file, If it's empty string, means have no password.

    Returns:
        str: The absolute path to the created ZIP file.
    """

    zipPathObj = Path(zipPath)
    dstPathObj = Path(dstFolderPath)

    with pyzipper.AESZipFile(str(zipPathObj)) as zipFile:
        if password:
            zipFile.setpassword(password.encode())
        zipFile.extractall(str(dstPathObj))

    return str(dstPathObj.resolve())


@Log.trace()
def csv_read(
    filePath: str,
    separator: str = ",",
    header: int | None = 0,
    indexColumn: int | str | None = None,
    encoding: Encoding = "utf-8",
) -> list[list[Any]]:
    """
    Reads a CSV file and returns its contents as a list of lists.

    Parameters:
        filePath: The path to the CSV file.
        separator: The character used to separate values.
        header: Row number(s) to use as the column names, or None.
        indexColumn: Column to set as index; can be column number or name.
        encoding: The encoding to use for reading the file.

    Returns:
        list[list[Any]]: The contents of the CSV file as a list of rows, where each row is a list of values.
    """
    return pandas.read_csv(
        filepath_or_buffer=filePath, sep=separator, header=header, index_col=indexColumn, encoding=encoding
    ).values.tolist()  # type: ignore - It should not be str.


@Log.trace()
def csv_write(
    listObj: list[list[Any]],
    filePath: str,
    separator: str = ",",
    addHeader: bool = False,
    addIndexColumn: bool = False,
    encoding: Encoding = "utf-8",
    overwriteIfExist: bool = False,
) -> None:
    """
    Writes a list of lists to a CSV file.

    Parameters:
        listObj: The data to write, as a list of lists.
        filePath: The path to the CSV file where data will be saved.
        separator: The character used to separate values.
        addHeader: Whether to write column names.
        addIndexColumn: Whether to write row names (index).
        encoding: The encoding to use for writing the file.
        overwriteIfExist: If False, raises an error if the file already exists.
    """
    if overwriteIfExist == False and Path(filePath).is_file():
        raise FileExistsError(f"There is a file in the destination path: {Path(filePath).resolve()}")
    pandas.DataFrame(data=listObj).to_csv(
        path_or_buf=filePath, sep=separator, header=addHeader, index=addIndexColumn, mode="w", encoding=encoding
    )


@Log.trace()
def ini_read_value(filePath: str, sectionName: str, optionName: str, encoding: Encoding = "utf-8") -> str:
    """
    Reads and returns the value of a given option under a specified section in an INI file.

    Parameters:
        filePath: The path to the INI file.
        sectionName: The section within the INI file where the option resides.
        optionName: The name of the option to read.
        encoding: The character encoding of the INI file.

    Returns:
        str: The value of the specified option.
    """
    iniObj = configparser.ConfigParser()
    iniObj.read(filenames=filePath, encoding=encoding)
    return iniObj.get(section=sectionName, option=optionName)


@Log.trace()
def ini_write_value(
    filePath: str, sectionName: str, optionName: str, optionValue: str, encoding: Encoding = "utf-8"
) -> None:
    """
    Writes a value to a specific option under a certain section in an INI file.

    If the section does not exist, it will be created.

    Parameters:
        filePath: The path to the INI file.
        sectionName: The section within the INI file to modify or create.
        optionName: The name of the option to modify or create.
        optionValue: The value to write to the option.
        encoding: The character encoding of the INI file.
    """
    iniObj = configparser.ConfigParser()
    iniObj.read(filenames=filePath, encoding=encoding)
    if iniObj.has_section(section=sectionName) == False:
        iniObj.add_section(section=sectionName)
    iniObj.set(section=sectionName, option=optionName, value=optionValue)
    with open(file=filePath, mode="w") as fileObj:
        iniObj.write(fileObj)


@Log.trace()
def ini_get_all_sections(filePath: str, encoding: Encoding = "utf-8") -> list[str]:
    """
    Retrieves a list of all option names within a specific section of an INI file.

    Parameters:
        filePath: The path to the INI file.
        sectionName: The section within the INI file.
        encoding: The character encoding of the INI file.

    Returns:
        list[str]: A list of option names within the specified section.
    """
    iniObj = configparser.ConfigParser()
    iniObj.read(filenames=filePath, encoding=encoding)
    return iniObj.sections()


@Log.trace()
def ini_get_all_options(filePath: str, sectionName: str, encoding: Encoding = "utf-8") -> list[str]:
    """
    Deletes a specific section from an INI file.

    Parameters:
        filePath: The path to the INI file.
        sectionName: The section to be removed.
        encoding: The character encoding of the INI file.
    """
    iniObj = configparser.ConfigParser()
    iniObj.read(filenames=filePath, encoding=encoding)
    return iniObj.options(section=sectionName)


@Log.trace()
def ini_delete_section(filePath: str, sectionName: str, encoding: Encoding = "utf-8") -> None:
    """
    Deletes a specific section from an INI file.

    Parameters:
        filePath: The path to the INI file.
        sectionName: The section to be removed.
        encoding: The character encoding of the INI file.
    """
    iniObj = configparser.ConfigParser()
    iniObj.read(filenames=filePath, encoding=encoding)
    iniObj.remove_section(section=sectionName)
    with open(file=filePath, mode="w") as fileObj:
        iniObj.write(fileObj)


@Log.trace()
def ini_delete_option(filePath: str, sectionName: str, optionName: str, encoding: Encoding = "utf-8") -> None:
    """
    Deletes a specific option from a section in an INI file.

    Parameters:
        filePath: The path to the INI file.
        sectionName: The section from which the option will be removed.
        optionName: The option to be removed.
        encoding: The character encoding of the INI file.
    """
    iniObj = configparser.ConfigParser()
    iniObj.read(filenames=filePath, encoding=encoding)
    iniObj.remove_option(section=sectionName, option=optionName)
    with open(file=filePath, mode="w") as fileObj:
        iniObj.write(fileObj)


@Log.trace()
def pdf_get_page_count(filePath: str, password: str = "") -> int:
    """
    Returns the total number of pages in a PDF file.

    Parameters:
        filePath: The path to the PDF file.
        password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.

    Returns:
        int: The total number of pages in the PDF.
    """
    if password == "":
        return len(PdfReader(stream=filePath, strict=False, password=None).pages)
    else:
        return len(PdfReader(stream=filePath, strict=False, password=password).pages)


@Log.trace()
def pdf_save_pages_as_images(
    filePath: str,
    password: str = "",
    saveFolderPath: str = "./",
    startPage: int = 1,
    endPage: int = 1,
    scale: float = 2.0,
) -> list[str]:
    """
    Saves specified pages of a PDF file as images in a specified folder.

    Parameters:
        filePath: The path to the PDF file.
        password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
        saveFolderPath: The directory to save the image files.
        startPage: The first page to convert to an image.
        endPage: The last page to convert to an image.
        scale: Scaling factor to increase resolution.

    Returns:
        list[str]: A list of paths to the saved image files.
    """
    with fitz.open(filePath) as doc:
        if password != "":
            doc.authenticate(password)
        listExtractedImagePath: list[str] = []

        os.makedirs(saveFolderPath, exist_ok=True)

        # Scaling matrix for higher resolution
        matrix = fitz.Matrix(scale, scale)

        for index in range(startPage - 1, endPage):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=matrix)  # type: ignore
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)  # type: ignore
            imageFileName = f"{Path(filePath).stem}_{index+1}.png"
            imageFilePath = os.path.join(saveFolderPath, imageFileName)
            img.save(imageFilePath, "PNG")
            listExtractedImagePath.append(str(Path(imageFilePath).resolve()))

    return listExtractedImagePath


@Log.trace()
def pdf_extract_images_from_pages(
    filePath: str,
    password: str = "",
    saveFolderPath: str = "./",
    format: Literal["png", "jpg", "jpeg", "bmp"] = "png",
    startPage: int = 1,
    endPage: int = 1,
) -> list[str]:
    """
    Extracts images from specified pages of a PDF and saves them in a specified format and folder.

    Parameters:
        filePath: The path to the PDF file.
        password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
        saveFolderPath: The directory to save the extracted images.
        format: The image format for saving extracted images. Can be 'png', 'jpg', 'jpeg', or 'bmp'.
        startPage: The first page to extract images from.
        endPage: The last page to extract images from.

    Returns:
        list[str]: A list of paths to the extracted image files.
    """
    with fitz.open(filePath, filetype="pdf") as doc:  # type: ignore
        if password != "":
            doc.authenticate(password)
        listExtractedImagePath: list[str] = []

        os.makedirs(saveFolderPath, exist_ok=True)

        for page_num in range(startPage - 1, endPage):
            page = doc.load_page(page_num)
            listImage = page.get_images(full=True)

            for imgIndex, img in enumerate(listImage, start=1):
                xref = img[0]
                base_image = doc.extract_image(xref)
                imageBytes = base_image["image"]

                # Construct image file path
                strImageFileName = f"image_page{page_num + 1}_index{imgIndex}.{format.lower()}"
                strImageFilePath = os.path.join(saveFolderPath, strImageFileName)

                img = Image.open(fp=io.BytesIO(imageBytes))

                # Convert and save in the desired format
                match format.lower():
                    case "png":
                        img.save(strImageFilePath, "PNG")
                    case "jpg":
                        img.save(strImageFilePath, "JPEG")
                    case "jpeg":
                        img.save(strImageFilePath, "JPEG")
                    case "bmp":
                        img.save(strImageFilePath, "BMP")
                    case _:
                        raise ValueError("Can only save these formats: png, jpg(jpeg), bmp")

                listExtractedImagePath.append(str(Path(strImageFilePath).resolve()))
    return listExtractedImagePath


@Log.trace()
def pdf_extract_text_from_pages(
    filePath: str,
    password: str = "",
    startPage: int = 1,
    endPage: int = 1,
) -> str:
    """
    Extracts text from specified pages of a PDF file.

    Parameters:
        filePath: The path to the PDF file.
        password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
        startPage: The first page to extract text from.
        endPage: The last page to extract text from.

    Returns:
        str: The extracted text from specified pages.
    """
    with fitz.open(filePath, filetype="pdf") as doc:  # type: ignore
        if password != "":
            doc.authenticate(password)
        text: str = ""
        for page_num in range(startPage - 1, endPage):
            page = doc.load_page(page_num)
            text += page.get_text()  # type: ignore
    return text


@Log.trace()
def pdf_extract_all_images(
    filePath: str, password: str = "", saveFolderPath: str = "./", format: Literal["png", "jpg", "jpeg", "bmp"] = "png"
) -> list[str]:
    """
    Extracts images in a PDF and saves them in a specified format and folder.

    Parameters:
        filePath: The path to the PDF file.
        password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
        saveFolderPath: The directory to save the extracted images.
        format: The image format for saving extracted images. Can be 'png', 'jpg', 'jpeg', or 'bmp'.

    Returns:
        list[str]: A list of paths to the extracted image files.
    """
    return pdf_extract_images_from_pages(
        filePath=filePath,
        password=password,
        saveFolderPath=saveFolderPath,
        format=format,
        startPage=1,
        endPage=pdf_get_page_count(filePath=filePath, password=password),
    )


@Log.trace()
def pdf_extract_all_text(filePath: str, password: str = "") -> str:
    """
    Extracts all text in a PDF.

    Parameters:
        filePath: The path to the PDF file.
        password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.

    Returns:
        str: The text in the PDF file.
    """
    return pdf_extract_text_from_pages(
        filePath=filePath,
        password=password,
        startPage=1,
        endPage=pdf_get_page_count(filePath=filePath, password=password),
    )


@Log.trace()
def pdf_merge(listFilePath: list[str], savePath: str) -> str:
    """
    Merges multiple PDF files into a single PDF file and saves it to a specified path.

    Parameters:
        listFilePath: A list of paths to the PDF files to be merged.
        savePath: The path to save the merged PDF file.

    Returns:
        str: The absolute path to the saved merged PDF file.
    """
    writer = PdfWriter()
    for strPath in listFilePath:
        reader = PdfReader(stream=strPath, strict=False, password=None)
        for page in reader.pages:
            writer.add_page(page=page)
    with open(file=savePath, mode="wb") as fileObj:
        writer.write(fileObj)

    return str(Path(savePath).resolve())


if __name__ == "__main__":
    wait_file_download(filePath="./123.png")
