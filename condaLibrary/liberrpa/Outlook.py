# FileName: Outlook.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictOutlookMailInfo, StrPath
from liberrpa.Common._Utils import normalize_attachment_paths
import win32com.client
from pathlib import Path
from typing import Literal
from datetime import datetime


def _add_attachments(
    mailObj: win32com.client.CDispatch,
    attachments: StrPath | list[StrPath] | None,
) -> None:
    for path in normalize_attachment_paths(attachments):
        mailObj.Attachments.Add(path)


@Log.trace()
def send_email(
    account: str,
    to: str,
    subject: str,
    body: str,
    bodyFormat: Literal["text", "html"] = "text",
    attachments: StrPath | list[StrPath] | None = None,
    cc: str | None = None,
    bcc: str | None = None,
) -> None:
    """
    Send an email using a specified Outlook account.

    Parameters:
        account: The email address of the Outlook account to send the email from.
        to: A semicolon-separated string of recipient email addresses.
        subject: The email subject.
        body: The email body content.
        bodyFormat: The format of the email body, either "text" or "html".
        attachments: File path or list of file paths to attach. Accepts str or PathLike[str].
        cc: A semicolon-separated string of CC recipient email addresses.
        bcc: A semicolon-separated string of BCC recipient email addresses.
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
            raise ValueError('The argument bodyFormat should be "text" or "html".')

    _add_attachments(mailObj=mail, attachments=attachments)

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
    searchText: str = "",
    limit: int = 1,
    onlyUnread: bool = False,
    markAsRead: bool = False,
) -> tuple[list[DictOutlookMailInfo], list[win32com.client.CDispatch]]:
    """
    Fetch emails from a specified Outlook account and folder.

    Parameters:
        account: The email account to fetch emails from.
        folder: The folder to fetch emails from.
        searchText: Text to search for in each email. If it is not empty, only emails containing this text in the subject, body, HTML body, sender email address, recipient addresses, CC, or BCC are returned. The search is performed by LiberRPA after emails are retrieved from Outlook, not by Outlook's Restrict filter syntax.
        limit: Maximum number of matched emails to return.
        onlyUnread: If True, retrieves only unread emails.
        markAsRead: If True, marks only the returned matched emails as read.

    Returns:
        tuple[list[DictOutlookMailInfo], list[win32com.client.CDispatch]]:
            A list of basic information dictionaries for each returned email.
            A list of Outlook email objects for further operations.
    """

    if limit < 1:
        raise ValueError("The argument 'limit' should be greater than or equal to 1.")

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

    searchTextLower = searchText.lower()

    for message in messages:
        if searchText:
            # Check if the searchText string is in any of the email properties
            boolMatched = (
                searchTextLower in str(message.Subject).lower()
                or searchTextLower in str(message.Body).lower()
                or searchTextLower in str(message.HTMLBody).lower()
                or searchTextLower in str(message.SenderEmailAddress).lower()
                or any(searchTextLower in str(recipient.Address).lower() for recipient in message.Recipients)
                or searchTextLower in str(message.CC or "").lower()
                or searchTextLower in str(message.BCC or "").lower()
            )
        else:
            boolMatched = True

        if not boolMatched:
            # Emails which do not match should not be handled.
            continue

        listEmail.append(message)

        if markAsRead:
            message.Unread = False

        if len(listEmail) >= limit:
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
    attachments: StrPath | list[StrPath] | None = None,
    replyAll: bool = True,
    newSubject: str | None = None,
) -> None:
    """
    Reply to an email.

    Parameters:
        emailObj: The Outlook email object to reply to.
        body: The reply body content.
        bodyFormat: The format of the email body, either "text" or "html".
        attachments: File path or list of file paths to attach. Accepts str or PathLike[str].
        replyAll: If True, replies to all recipients. If False, replies only to the sender.
        newSubject: A custom subject for the reply. If None or empty, keeps Outlook's default reply subject.
    """
    reply: win32com.client.CDispatch = emailObj.ReplyAll() if replyAll else emailObj.Reply()

    if newSubject:
        reply.Subject = newSubject

    match bodyFormat:
        case "text":
            reply.Body = body + reply.Body
        case "html":
            reply.HTMLBody = body + reply.HTMLBody
        case _:
            raise ValueError('The argument bodyFormat should be "text" or "html".')

    _add_attachments(mailObj=reply, attachments=attachments)

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
def download_attachments(emailObj: win32com.client.CDispatch, downloadPath: StrPath) -> list[str]:
    """
    Download all attachments of an email.

    Parameters:
        emailObj: The win32com.client.CDispatch objects to download its attachments.
        downloadPath: The folder to save download files. Accepts str or PathLike[str].

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
    listBasicInfo, listEmail = get_email_list(account="XXXX@qq.com", folder="草稿", limit=1)
    Log.debug(listBasicInfo)
    # print(download_attachments(emailObj=listEmail[0], downloadPath="./emailtest/"))
    # delete_email(listEmail[0])
    # print(get_folder_list(account="XXXX@qq.com"))
    # move_email(account="XXXX@qq.com",emailObj=listEmail[0],folder="Junk")
    reply_to_email(emailObj=listEmail[0], body="Reply test", bodyFormat="text", newSubject="New Subject Test")
