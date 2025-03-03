# FileName: Outlook.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictOutlookMailInfo
import win32com.client
from pathlib import Path
from typing import Literal
from datetime import datetime


@Log.trace()
def send_email(
    account: str,
    to: str,
    subject: str,
    body: str,
    bodyFormat: Literal["text", "html"] = "text",
    attachments: str | list[str] | None = None,
    cc: str | None = None,
    bcc: str | None = None,
) -> None:
    """
    Send an email using a specified Outlook account.

    Parameters:
        account: The email address of the account to send the email from.
        to: A semicolon-separated string of the recipient(s) of the email.
        subject: The subject of the email.
        body: The body content of the email.
        bodyFormat: The format of the email body ('text' or 'html').
        attachments: Path(s) to file(s) to attach. Can be a single path, a list of paths or None.
        cc: A semicolon-separated string of the CC recipient(s) of the email.
        bcc: A semicolon-separated string of the BCC recipient(s) of the email.
    """

    outlook = win32com.client.Dispatch("Outlook.Application")
    mapi = outlook.GetNamespace("MAPI")

    selectAccount = None
    for acc in mapi.Accounts:
        if acc.SmtpAddress.lower() == account.lower():
            selectAccount = acc
            break
    if not selectAccount:
        raise ValueError(f"No account found for email: {account}")

    mail = outlook.CreateItem(0)
    mail.SentOnBehalfOfName = selectAccount.SmtpAddress

    mail.To = to
    if cc is not None:
        mail.CC = cc
    if bcc is not None:
        mail.BCC = bcc
    mail.Subject = subject

    match bodyFormat:
        case "text":
            mail.Body = body
        case "html":
            mail.HTMLBody = body
        case _:
            raise ValueError(f"The argument bodyFormat should be 'text' or 'html'.")

    if isinstance(attachments, str):
        if attachments != "":
            mail.Attachments.Add(str(Path(attachments).absolute()))
    elif isinstance(attachments, list):
        for strPath in attachments:
            if strPath != "":
                mail.Attachments.Add(str(Path(strPath).absolute()))
    else:
        # None
        pass

    mail.Send()


@Log.trace()
def get_folder_list(account: str) -> list[str]:
    """
    Retrieves a list of all folders from the Outlook account.

    Parameters:
        account: The email account to fetch folder names from.

    Returns:
        list[str]: A list of folder names.
    """
    mapi: win32com.client.CDispatch = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

    selectAccount = None
    for acc in mapi.Accounts:
        if acc.SmtpAddress.lower() == account.lower():
            selectAccount = acc
            break
    if not selectAccount:
        raise ValueError(f"No account found for email: {account}")

    listFolder = mapi.Folders(selectAccount.DeliveryStore.DisplayName).Folders
    listFolderName = [folder.Name for folder in listFolder]

    return listFolderName


@Log.trace()
def get_email_list(
    account: str,
    folder: str = "INBOX",
    filter: str = "",
    numToGet: int = 1,
    onlyUnread: bool = False,
    markAsRead: bool = False,
) -> tuple[list[DictOutlookMailInfo], list[win32com.client.CDispatch]]:
    """
    Fetch a list of emails from a specified Outlook account and folder.

    Parameters:
        account: The email account to fetch emails from.
        folder: The folder to fetch emails from.
        filter: A string to filter emails based on their properties.
        numToGet: Maximum number of emails to fetch.
        onlyUnread: Whether to retrieve only unread emails.
        markAsRead: Whether to mark retrieved emails as read.

    Returns:
        tuple[list[DictOutlookMailInfo],list[win32com.client.CDispatch]]:
            A list of basic information dictionaries for each email, adhering to the DictOutlookMailInfo structure.
            A list of email objects.
    """

    mapi: win32com.client.CDispatch = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

    selectAccount: win32com.client.CDispatch | None = None
    for acc in mapi.Accounts:
        if acc.SmtpAddress.lower() == account.lower():
            selectAccount = acc
            break
    if not selectAccount:
        raise ValueError(f"No account found for email: {account}")

    messages: win32com.client.CDispatch = mapi.Folders(selectAccount.DeliveryStore.DisplayName).Folders(folder).Items

    if onlyUnread:
        messages = messages.Restrict("[Unread] = True")

    messages.Sort("[ReceivedTime]", True)

    listEmail: list[win32com.client.CDispatch] = []
    listBasicInfo: list[DictOutlookMailInfo] = []
    for message in messages:
        if filter != "":
            # Check if the filter string is in any of the email properties
            if (
                filter in message.Subject
                or filter in message.Body
                or filter in message.HTMLBody
                or filter.lower() in message.SenderEmailAddress.lower()
                or any(filter.lower() in recipient.Address.lower() for recipient in message.Recipients)
                or filter.lower() in (message.CC if message.CC else "").lower()
                or filter.lower() in (message.BCC if message.BCC else "").lower()
            ):
                listEmail.append(message)
        else:
            listEmail.append(message)

        if markAsRead:
            message.Unread = False

        if len(listEmail) >= numToGet:
            break

    for email in listEmail:
        dictTemp: DictOutlookMailInfo = {
            "Subject": email.Subject,
            "Body": email.Body,
            "HTMLBody": email.HTMLBody,
            "SenderEmailAddress": email.SenderEmailAddress,
            "SenderName": email.SenderName,
            "To": email.To,
            "CC": email.CC,
            "BCC": email.BCC,
            "ReceivedTime": email.ReceivedTime,
            "SentOn": email.SentOn,
            "Importance": email.Importance,
            "Attachments": str([ele.FileName for ele in email.Attachments]),
            "Size": email.Size,
        }

        if isinstance(dictTemp["ReceivedTime"], datetime):
            dictTemp["ReceivedTime"] = dictTemp["ReceivedTime"].strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(dictTemp["SentOn"], datetime):
            dictTemp["SentOn"] = dictTemp["SentOn"].strftime("%Y-%m-%d %H:%M:%S")

        match dictTemp["Importance"]:
            case 1:
                dictTemp["Importance"] = "high"
            case 2:
                dictTemp["Importance"] = "normal"
            case _:
                dictTemp["Importance"] = "low"

        listBasicInfo.append(dictTemp)

    return (listBasicInfo, listEmail)


@Log.trace()
def move_email(account: str, emailObj: win32com.client.CDispatch, folder: str) -> None:
    """
    Move an email by its uid.

    Parameters:
        account: The email account.
        emailObj: The win32com.client.CDispatch objects to move.
        folder: The name of the folder to move.
    """
    mapi = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    selectAccount = None
    for acc in mapi.Accounts:
        if acc.SmtpAddress.lower() == account.lower():
            selectAccount = acc
            break
    if not selectAccount:
        raise ValueError(f"No account found for email: {account}")

    # Access the root folder of the account's delivery store
    rootFolder = mapi.Folders[selectAccount.DeliveryStore.DisplayName]

    # Access the target folder
    # Note: This assumes 'targetFolder' is directly under the root. If it's nested, additional logic is needed.
    destinationFolder = rootFolder.Folders[folder]
    emailObj.Move(destinationFolder)


@Log.trace()
def reply_to_email(
    emailObj: win32com.client.CDispatch,
    body: str,
    bodyFormat: Literal["text", "html"] = "text",
    attachments: str | list[str] | None = None,
    replyAll: bool = True,
    newSubject: str | None = None,
) -> None:
    """
    Reply an email.

    Parameters:
        emailObj: The win32com.client.CDispatch objects to reply.
        body: The body content of the email.
        bodyFormat: The format of the email body ('text' or 'html').
        attachments: Path(s) to file(s) to attach. Can be a single path ,a list of paths or None.
        replyAll: Whether to reply all recipients.
        newSubject: A custom subject for the reply.
    """
    reply: win32com.client.CDispatch = emailObj.ReplyAll() if replyAll else emailObj.Reply()

    if newSubject is not None and newSubject != "":
        reply.Subject = newSubject

    match bodyFormat:
        case "text":
            reply.Body = body + reply.Body
        case "html":
            reply.HTMLBody = body + reply.HTMLBody
        case _:
            raise ValueError(f"The argument bodyFormat should be 'text' or 'html'.")

    if isinstance(attachments, str):
        if attachments != "":
            reply.Attachments.Add(str(Path(attachments).absolute()))
    elif isinstance(attachments, list):
        for strPath in attachments:
            if strPath != "":
                reply.Attachments.Add(str(Path(strPath).absolute()))
    else:
        # None
        pass

    reply.Send()


@Log.trace()
def delete_email(emailObj: win32com.client.CDispatch) -> None:
    """
    Delete an email.

    Parameters:
        emailObj: A win32com.client.CDispatch objects.
    """
    emailObj.delete()


@Log.trace()
def download_attachments(emailObj: win32com.client.CDispatch, downloadPath: str) -> list[str]:
    """
    Download all attachments of an email.

    Parameters:
        emailObj: The win32com.client.CDispatch objects to download its attachments.
        downloadPath: The folder to save download files.

    Returns:
        list[str]: A list contains the path of all attachments.
    """
    listFilePath: list[str] = []
    Path(downloadPath).mkdir(parents=True, exist_ok=True)
    for attachment in emailObj.attachments:
        strFilePath = Path(downloadPath).joinpath(attachment.FileName)
        attachment.SaveAsFile(str(strFilePath.absolute()))
        listFilePath.append(str(strFilePath.absolute()))
    return listFilePath


if __name__ == "__main__":
    # send_email(
    #     account="XXXX@qq.com",
    #     to="XXXX@qq.com",
    #     subject="testOutlook3",
    #     body="<H1>Body</H1>",
    #     bodyFormat="html",
    #     attachment=["./liberrpa/text.txt"],
    #     cc="XXXX@qq.com;YYYY@qq.com",
    #     bcc=None,
    # )
    listBasicInfo, listEmail = get_email_list(account="XXXX@qq.com", folder="草稿", numToGet=1)
    Log.debug(listBasicInfo)
    # print(download_attachments(emailObj=listEmail[0], downloadPath="./emailtest/"))
    # delete_email(listEmail[0])
    # print(get_folder_list(account="XXXX@qq.com"))
    # move_email(account="XXXX@qq.com",emailObj=listEmail[0],folder="Junk")
    reply_to_email(emailObj=listEmail[0], body="Reply test", bodyFormat="text",newSubject="New Subject Test")
