# FileName: Web.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Data import sanitize_filename
import requests
from pathlib import Path
import re
from urllib.parse import urlparse
import os
from typing import Any
from copy import deepcopy

dictCookies: dict[str, str] = {}
dictHeaders: dict[str, str] = {}


@Log.trace()
def set_cookies(cookies: dict[str, str]) -> None:
    """
    Sets the cookies to be used in subsequent HTTP requests.

    Parameters:
        cookies (dict[str, str]): A dictionary of cookies to set.
    """
    global dictCookies
    dictCookies = deepcopy(cookies)


@Log.trace()
def set_headers(headers: dict[str, str]) -> None:
    """
    Sets the headers to be used in subsequent HTTP requests.

    Parameters:
        headers (dict[str, str]): A dictionary of headers to set.
    """
    global dictHeaders
    dictHeaders = deepcopy(headers)


@Log.trace()
def get(
    url: str,
    params: dict[str, str] | list[tuple[str, str]] | str | bytes | None = None,
    timeout: int = 60,
) -> str:
    """
    Sends an HTTP GET request to the given URL with the specified parameters, headers, and cookies.

    Parameters:
        url: The URL to send the GET request to.
        params: The query parameters to include in the request.
        timeout: The timeout duration for the request, in seconds.

    Returns:
        str: The response body as a string if the request is successful.
    """
    response = requests.get(url=url, params=params, headers=dictHeaders, cookies=dictCookies, timeout=timeout)
    response.raise_for_status()
    return response.text


@Log.trace()
def post(
    url: str,
    data: str | bytes | dict[str, str] | list[tuple[str, str]] | None = None,
    json: Any = None,
    files: dict[str, tuple[str, Any, str]] | None = None,
    params: dict[str, str] | list[tuple[str, str]] | str | bytes | None = None,
    timeout: int = 60,
) -> str:
    """
    Sends an HTTP POST request to the given URL with the specified data, JSON, files, and query parameters.

    Parameters:
        url: The URL to send the POST request to.
        data: The form data to include in the body of the request. Can be a string, bytes, dictionary, or list of tuples.
        json: The JSON data to include in the body of the request.
        files: Files to upload via multipart form data. Should be a dictionary where each key is a file field name and the value is a tuple (filename, file-object, file-type).
        params: The query parameters to include in the request. Can be a dictionary, list of tuples, string, or bytes.
        timeout: The timeout duration for the request, in seconds.

    Returns:
        str: The response body as a string if the request is successful.
    """
    response = requests.post(
        url=url,
        data=data,
        json=json,
        files=files,
        params=params,
        headers=dictHeaders,
        cookies=dictCookies,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


@Log.trace()
def download_file(
    url: str,
    folderPath: str,
    params: dict[str, str] | list[tuple[str, str]] | str | bytes | None = None,
    timeout: int = 60,
    stream: bool = False,
    overwriteIfExist: bool = False,
) -> str:
    """
    Downloads a file from the given URL and saves it to the specified folder.

    Parameters:
        url: The URL of the file to download.
        folderPath: The directory where the file will be saved.
        params: Optional query parameters to include in the request.
        timeout: Timeout duration for the request, in seconds.
        stream: Whether to stream the download (useful for large files, to avoid excessive memory usage).
        overwriteIfExist: If set to True, the destination file will be overwritten if it already exists; if False, a FileExistsError will be raised if the destination file exists.

    Returns:
        str: The absolute path of the downloaded file.
    """
    response = requests.get(
        url=url, params=params, headers=dictHeaders, cookies=dictCookies, stream=stream, timeout=timeout
    )

    response.raise_for_status()

    # Extract filename from Content-Disposition header if available
    contentDisposition = response.headers.get("Content-Disposition")

    if contentDisposition:
        # If 'Content-Disposition' is provided and contains a filename, extract it
        listFileName = re.findall('filename="(.+)"', contentDisposition)
        strFileName = listFileName[0] if listFileName else "download.file"
    else:
        # Fallback to extracting the filename from the URL path
        strFileName = os.path.basename(urlparse(url).path) or "download.file"

    # Create the target folder if it doesn't exist.
    Path(folderPath).mkdir(parents=True, exist_ok=True)

    strFilePath = Path(folderPath).joinpath(sanitize_filename(strFileName))

    if overwriteIfExist == False and Path(strFilePath).is_file():
        raise FileExistsError(f"There is a file in the destination path: {Path(strFilePath).resolve()}")

    with open(file=strFilePath, mode="wb") as fileObj:
        if stream:
            # If streaming is enabled, write the file in chunks
            for chunk in response.iter_content(chunk_size=8192):
                fileObj.write(chunk)
        else:
            # If streaming is not enabled, write the entire content at once
            fileObj.write(response.content)

    return str(strFilePath.absolute())


@Log.trace()
def upload_file(
    url: str,
    filePath: str,
    data: str | bytes | dict[str, str] | list[tuple[str, str]] | None = None,
    json: Any = None,
    params: dict[str, str] | list[tuple[str, str]] | str | bytes | None = None,
    timeout: int = 60,
) -> str:
    """
    Send a POST request to the given URL with a file, data, and other optional parameters.

    Parameters:
        url: The URL to send the request to.
        filePath: The path to the file to be uploaded.
        data: Optional form data to include in the request.
        json: Optional JSON data to include in the request body.
        params: Optional query parameters to include in the request URL.
        timeout: The request timeout duration in seconds.

    Returns:
        str: The server's response text.
    """
    with open(file=filePath, mode="rb") as fileObj:
        files = {"file": fileObj}
        response = requests.post(
            url=url,
            data=data,
            json=json,
            params=params,
            files=files,
            headers=dictHeaders,
            cookies=dictCookies,
            timeout=timeout,
        )

    response.raise_for_status()

    return response.text


if __name__ == "__main__":
    # print(get(url="https://jsonplaceholder.typicode.com/posts",params={"userId":"1"},timeout=60))
    # print(
    #     post(
    #         url="https://jsonplaceholder.typicode.com/posts",
    #         json={"title": "foo", "body": "bar", "userId": 1},
    #         timeout=60,
    #     )
    # )
    # print(
    #     download_file(
    #         url="https://developer.mozilla.org/static/media/mdn_contributor.14a24dcfda486f000754.png",
    #         folderPath="./",
    #         stream=True,
    #         overwriteIfExist=True,
    #     )
    # )
    print(upload_file(url="https://httpbin.org/post", filePath="./project.json"))
