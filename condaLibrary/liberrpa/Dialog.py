# FileName: Dialog.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command
from liberrpa.Common._Exception import QtError

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from typing import Literal, overload, get_args

type FileTypes = list[tuple[str, str | list[str] | tuple[str, ...]]]

type MessageBoxType = Literal["info", "warning", "error", "question"]
type InfoButton = Literal["ok", "okcancel", "yesno", "retrycancel"]
type MessageBoxResponse = Literal["ok", "yes", "no"] | bool


_DEFAULT_FILETYPES: FileTypes = [("All Files", "*.*")]


@Log.trace()
def show_notification(title: str, message: str, duration: int = 1, wait: bool = True) -> None:
    """
    Show a notification on at bottom-right of the primary screen.

    Parameters:
        title: The notification's title.
        message: The notification's content. If it's too long, some text may be invisible.
        duration: Duration to show the notification (seconds).
        wait: Whether to wait the notification disappear.
    """

    # Local Server has done the check, but I think checking it here is better.
    if message is None or message == "":
        raise ValueError("The message can't be empty or None.")
    if duration <= 0:
        raise ValueError("The duration should larger than 0.")

    try:
        dictCommand = {
            "commandName": "show_notification",
            "title": title,
            "message": message,
            "duration": duration,
            "wait": wait,
        }

        send_command(eventName="qt_command", command=dictCommand)
    except QtError:
        raise
    except Exception:
        # If Qt dialog is unavailable, fall back to the local tkinter dialog.
        pass


@Log.trace()
def open_file(
    folder: None | str = None,
    title: str = "open a file",
    filetypes: FileTypes | None = None,
) -> str:
    """
    Opens a file dialog to select a file.
    A Value Error will be raised if no file selected.

    Parameters:
        folder: The directory that the dialog opens in. If None, defaults to the current working directory.
        title: The title of the dialog window.
        filetypes: A list of tuples defining the file types to display. Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files. If None, all files are shown.

    Returns:
        str: The file path selected by the user.
    """

    filetypes = _DEFAULT_FILETYPES.copy() if filetypes is None else filetypes

    root = tk.Tk()
    root.withdraw()

    strFilePath = filedialog.askopenfilename(initialdir=folder, title=title, filetypes=filetypes)
    root.destroy()

    if not strFilePath:
        raise ValueError("No file selected.")
    return strFilePath


@Log.trace()
def open_files(
    folder: None | str = None,
    title: str = "open files",
    filetypes: FileTypes | None = None,
) -> list[str]:
    """
    Open a file dialog to select files.
    A Value Error will be raised if no files selected.

    Parameters:
        folder: The directory that the dialog opens in. If None, defaults to the current working directory.
        title: The title of the dialog window.
        filetypes: A list of tuples defining the file types to display. Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files. If None, all files are shown.

    Returns:
        list[str]: The files' paths selected by the user.
    """

    filetypes = _DEFAULT_FILETYPES.copy() if filetypes is None else filetypes

    root = tk.Tk()
    root.withdraw()

    listFilePath = filedialog.askopenfilenames(initialdir=folder, title=title, filetypes=filetypes)
    root.destroy()
    if len(listFilePath) == 0:
        raise ValueError("No file selected.")
    return list(listFilePath)


@Log.trace()
def save_as(
    folder: None | str = None,
    title: str = "save as",
    filetypes: FileTypes | None = None,
) -> str:
    """
    Open a file dialog to save file. It just return the save path string, then you should use other logic to save a file by the path.
    A Value Error will be raised if no file name specified.

    Parameters:
        folder: The directory that the dialog opens in. If None, defaults to the current working directory.
        title: The title of the dialog window.
        filetypes: A list of tuples defining the file types to display. Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files. If None, all files are shown.

    Returns:
        str: The file path selected by the user.
    """

    filetypes = _DEFAULT_FILETYPES.copy() if filetypes is None else filetypes

    root = tk.Tk()
    root.withdraw()

    strFilePath = filedialog.asksaveasfilename(initialdir=folder, title=title, filetypes=filetypes)
    root.destroy()
    if not strFilePath:
        raise ValueError("No file name specified.")
    return strFilePath


@Log.trace()
def show_text_input_box(title: str, prompt: str, initialvalue: str = "") -> str:
    """
    Displays a dialog box that prompts the user to enter text.
    A Value Error will be raised if no text input.

    Parameters:
        title: The title of the dialog box.
        prompt: The text prompt displayed within the dialog box.
        initialvalue: The initial placeholder text within the input field.

    Returns:
        str: The text entered by the user.
    """
    root = tk.Tk()
    root.withdraw()

    strInputText = simpledialog.askstring(title=title, prompt=prompt, initialvalue=initialvalue)

    root.destroy()
    if not strInputText:
        raise ValueError("No text input.")
    return strInputText


@overload
def show_message_box(
    title: str,
    message: str,
    *,
    type: Literal["info"] = "info",
    infoButton: Literal["ok"] = "ok",
) -> Literal["ok"]: ...


@overload
def show_message_box(
    title: str,
    message: str,
    *,
    type: Literal["info"] = "info",
    infoButton: Literal["okcancel", "yesno", "retrycancel"],
) -> bool: ...


@overload
def show_message_box(
    title: str,
    message: str,
    *,
    type: Literal["info"] = "info",
    infoButton: InfoButton,
) -> Literal["ok"] | bool: ...


@overload
def show_message_box(
    title: str,
    message: str,
    *,
    type: Literal["warning", "error"],
) -> Literal["ok"]: ...


@overload
def show_message_box(
    title: str,
    message: str,
    *,
    type: Literal["question"],
) -> Literal["yes", "no"]: ...


@Log.trace()
def show_message_box(
    title: str,
    message: str,
    *,
    type: MessageBoxType = "info",
    infoButton: InfoButton | None = None,
) -> MessageBoxResponse:
    """
    Show a message box and return the user's response.

    Parameters:
        title: The title of the dialog window.
        message: The main content of the dialog window.
        type: The message box type, one of ["info", "warning", "error", "question"].
        infoButton: The button type for type="info", one of ["ok", "okcancel", "yesno", "retrycancel"].

    Returns:
        MessageBoxResponse: The user's response. For type="info" with "ok", "warning", or "error", returns "ok". For type="info" with "okcancel", "yesno", or "retrycancel", returns bool. For type="question", returns "yes" or "no".
    """

    if type != "info" and infoButton is not None:
        raise ValueError("infoButton is only valid when type='info'.")

    root = tk.Tk()
    root.withdraw()  # Hide the main window

    try:
        match type:
            case "info":
                button = infoButton or "ok"
                match button:
                    case "ok":
                        response = messagebox.showinfo(title, message)
                        # Return "ok"
                    case "okcancel":
                        response = messagebox.askokcancel(title, message)
                    case "yesno":
                        response = messagebox.askyesno(title, message)
                    case "retrycancel":
                        response = messagebox.askretrycancel(title, message)
                    case _:
                        raise ValueError(f"infoButton should be one of {list(get_args(InfoButton.__value__))}.")
                    # Return bool
            case "warning":
                response = messagebox.showwarning(title, message)
                # Return "ok"
            case "error":
                response = messagebox.showerror(title, message)
                # Return "ok"
            case "question":
                response = messagebox.askquestion(title, message)
                # Return "yes" or "no"
            case _:
                raise ValueError(f"type should be one of {list(get_args(MessageBoxType.__value__))}.")

    finally:
        root.destroy()

    if response not in ("ok", "yes", "no", True, False):
        raise ValueError(f"Unexpected message box response: {response!r}")

    return response


if __name__ == "__main__":
    # print("Start")
    """ show_notification(title="LiberRPA", message="", duration=3, wait=False)
    import time

    for i in range(0, 5, 1):
        time.sleep(1)
        print(i)

    show_notification(title="LiberRPA", message="456", duration=3, wait=False)
    time.sleep(1)
    show_notification(title="LiberRPA", message="789", duration=3, wait=True) """
    # print("Done")
    # print(open_file(folder=R"C:\software", title="Open a file", filetypes=[("some file", "*.zip")]))
    # print(open_files(folder=R"C:\software", title="Open a file", filetypes=[("some file", "*.*")]))
    # print(save_as(folder=R"C:\software", title="save a file", filetypes=[("some file", "*.*")]))
    # print(repr(show_text_input_box(title="Input something.", prompt="Prompt here.", initialvalue="123")))
    temp: InfoButton = "okcancel"
    # print(show_message_box(title="Title", message="Message here.", infoButton=temp))
    print(show_message_box("TTT", "MMM", type="error"))
    # print(list(get_args(InfoButton.__value__)))
