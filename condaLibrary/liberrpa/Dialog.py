# FileName: Dialog.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import multiprocessing

processName = multiprocessing.current_process().name
from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command
from liberrpa.Common._Exception import QtError

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import time
from typing import Literal


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

    try:
        dictCommand = {
            "commandName": "show_notification",
            "title": title,
            "message": message,
            "duration": duration,
            "wait": wait,
        }

        send_command(eventName="qt_command", command=dictCommand)
    except QtError as e:
        raise e
    except Exception as e:
        pass


@Log.trace()
def open_file(
    folder: None | str = None,
    title: str = "open a file",
    filetypes: list[tuple[str, str | list[str] | tuple[str, ...]]] = [("All Files", "*.*")],
) -> str:
    """
    Opens a file dialog to select a file.
    A Value Error will be raised if no file selected.

    Parameters:
        folder: The directory that the dialog opens in. If None, defaults to the current working directory.
        title: The title of the dialog window.
        filetypes: A list of tuples defining the file types to display.

            Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files.

    Returns:
        str: The file path selected by the user. Returns an empty string if the dialog is cancelled.
    """
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
    filetypes: list[tuple[str, str | list[str] | tuple[str, ...]]] = [("All Files", "*.*")],
) -> list[str]:
    """
    Open a file dialog to select files.
    A Value Error will be raised if no files selected.

    Parameters:
        folder: The directory that the dialog opens in. If None, defaults to the current working directory.
        title: The title of the dialog window.
        filetypes: A list of tuples defining the file types to display.

            Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files.

    Returns:
        list[str]: The files' paths selected by the user. Returns an empty list if the dialog is cancelled.
    """
    root = tk.Tk()
    root.withdraw()

    listFilePath = filedialog.askopenfilenames(initialdir=folder, title=title, filetypes=filetypes)
    root.destroy()
    if len(listFilePath) == 0:
        raise ValueError("No files selected.")
    return list(listFilePath)


@Log.trace()
def save_as(
    folder: None | str = None,
    title: str = "save as",
    filetypes: list[tuple[str, str | list[str] | tuple[str, ...]]] = [("All Files", "*.*")],
) -> str:
    """
    Open a file dialog to save file. It just return the save path string, then you should use other logic to save a file by the path.
    A Value Error will be raised if no file name specified.

    Parameters:
        folder: The directory that the dialog opens in. If None, defaults to the current working directory.
        title: The title of the dialog window.
        filetypes: A list of tuples defining the file types to display.

            Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files.

    Returns:
        str: The file path selected by the user. Returns an empty string if the dialog is cancelled.
    """
    root = tk.Tk()
    root.withdraw()

    strFilePath = filedialog.asksaveasfilename(initialdir=folder, title=title, filetypes=filetypes)
    root.destroy()
    if not strFilePath:
        raise ValueError("No file name specified.")
    return strFilePath


@Log.trace()
def show_text_input_box(title: str, prompt: str, initialvalue: str = "") -> str | None:
    """
    Displays a dialog box that prompts the user to enter text.
    A Value Error will be raised if no text input.

    Parameters:
        title: The title of the dialog box.
        prompt: The text prompt displayed within the dialog box.
        initialvalue: The initial placeholder text within the input field.

    Returns:
        str | None: The text entered by the user, or None if the dialog is closed without an entry.
    """
    root = tk.Tk()
    root.withdraw()

    strInputText = simpledialog.askstring(title=title, prompt=prompt, initialvalue=initialvalue)

    root.destroy()
    if not strInputText:
        raise ValueError("No text input.")
    return strInputText


@Log.trace()
def show_message_box(
    title: str,
    message: str,
    type: Literal["info", "warning", "error", "question"] = "info",
    infoButton: Literal["ok", "okcancel", "yesno", "retrycancel"] = "ok",
) -> Literal["ok", "yes", "no", True, False]:
    """
    Shows a message box with specified title, message, icon, and button type.

    The function displays a message box and returns the user's response.

    The 'type' parameter changes the icon shown in the message box.

    The 'infoButton' parameter only has an effect when 'type' is 'info'; it changes the set of buttons available.

    Parameters:
        title: The title of the dialog window.
        message: The main content of the dialog window.
        type: The icon type of the message box, one of ['info', 'warning', 'error', 'question'].
        infoButton: The button type when 'type' is 'info', one of ['ok', 'okcancel', 'yesno', 'retrycancel'].

    Returns:
        "ok"|"yes"|"no"|True|False:
            For button types like 'okcancel', 'yesno', 'retrycancel', indicating the user's choice, it will return bool;
            For the 'ok' button type, and for 'question' with responses like "yes" or "no", it will return str.
    """
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    match type:
        case "info":
            match infoButton:
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
                    raise ValueError("infoButton should be one of ['ok', 'okcancel', 'yesno', 'retrycancel'].")
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
            raise ValueError("type should be one of ['info', 'warning', 'error', 'question'].")

    root.destroy()
    return response  # type: ignore


if __name__ == "__main__":

    # print("Start")
    show_notification(title="LiberRPA", message="", duration=3, wait=False)
    import time

    for i in range(0, 5, 1):
        time.sleep(1)
        print(i)

    show_notification(title="LiberRPA", message="456", duration=3, wait=False)
    time.sleep(1)
    show_notification(title="LiberRPA", message="789", duration=3, wait=True)
    # print("Done")
    # print(open_file(folder=R"C:\software", title="Open a file", filetypes=[("some file", "*.zip")]))
    # print(open_files(folder=R"C:\software", title="Open a file", filetypes=[("some file", "*.*")]))
    # print(save_as(folder=R"C:\software", title="save a file", filetypes=[("some file", "*.*")]))
    # print(repr(show_text_input_box(title="Input something.", prompt="Prompt here.", initialvalue="123")))
    # print(show_message_box(title="Title", message="Message here.", type="info", infoButton="ok"))
