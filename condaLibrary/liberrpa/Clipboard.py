# FileName: Clipboard.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log

from PIL import Image, ImageGrab
import io
import win32clipboard
import pyperclip


@Log.trace()
def get_text() -> str:
    """
    Retrieves text from the clipboard.

    Returns:
        str: The text currently stored in the clipboard.
    """
    return pyperclip.paste()


@Log.trace()
def set_text(text: str) -> None:
    """
    Places a string into the clipboard, making it the current clipboard text.

    Parameters:
        text: The string to be set to the clipboard.
    """
    if not isinstance(text, str):
        raise ValueError(f"The argument text({text}) is not a string(type: {type(text)})")
    if text == "":
        Log.warning("The argument text is an empty string.")
    return pyperclip.copy(text)


@Log.trace()
def save_image(savePath: str) -> None:
    """
    Saves an image from the clipboard to a specified path.

    If there are multiple or no images, it throws an exception.

    Parameters:
        savePath: The file path where the image should be saved.
    """
    imageTemp = ImageGrab.grabclipboard()
    if isinstance(imageTemp, Image.Image):
        imageTemp.save(fp=savePath)
    elif isinstance(imageTemp, list):
        raise SystemError("Not support saving multiple images.")
    else:
        raise LookupError("Not found image in clipboard.")


@Log.trace()
def set_image(imagePath: str) -> None:
    """
    Places an image from a specified file into the clipboard.

    Parameters:
        imagePath: The path to the image file to be set to the clipboard.
    """
    try:
        image = Image.open(imagePath)
    except FileNotFoundError:
        raise ValueError(f"Image file not found: {imagePath}")
    except Exception as e:
        raise ValueError(f"Error opening image: {e}")

    output = io.BytesIO()
    image.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]  # BMP file header is 14 bytes
    output.close()

    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()


if __name__ == "__main__":
    # set_image(imagePath=R"C:\Users\huhar\Desktop\123.jpg")
    print(repr(get_text()))
    # set_text(text="")
    # save_image(savePath="./123.png")
