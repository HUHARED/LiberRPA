# FileName: Mail.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictImapMailInfo
from liberrpa.Common._Exception import MailError
from imapclient import IMAPClient
from mailparser import parse_from_bytes, MailParser
from pathlib import Path
import base64
import yagmail
from datetime import datetime
from typing import Literal


@Log.trace()
def send_by_SMTP(
    user: str,
    password: str,
    to: str,
    subject: str,
    content: str,
    host: str,
    port: int = 465,
    attachments: str | list[str] | Path | None = None,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    bodyFormat: Literal["text", "html"] = "text",
    ssl=True,
    encoding: str = "utf-8",
) -> None:
    """
    Sends an email via SMTP with optional attachments and HTML content.

    Parameters:
        user: The SMTP username.
        password: The SMTP password.
        to: Recipient email address or list of addresses.
        subject: Email subject.
        content: Main email body content. Can be plain text or HTML.
        host: SMTP server host.
        port: SMTP server port.
        attachments: File path or list of file paths to be attached.
        cc: Email address or list of addresses for CC.
        bcc: Email address or list of addresses for BCC.
        bodyFormat: The format of the email body ('text' or 'html').
        ssl: Use SSL for the SMTP connection.
        encoding: Character encoding for the email.
    """
    yag = yagmail.SMTP(user=user, password=password, host=host, port=port, smtp_ssl=ssl, encoding=encoding)
    match bodyFormat:
        case "text":
            yag.send(
                to=to, subject=subject, contents=content, attachments=attachments, cc=cc, bcc=bcc, prettify_html=False
            )
        case "html":
            yag.send(
                to=to, subject=subject, contents=content, attachments=attachments, cc=cc, bcc=bcc, prettify_html=True
            )
        case _:
            raise ValueError(f"The argument bodyFormat should be 'text' or 'html'.")


@Log.trace()
def IMAP_login(
    username: str,
    password: str,
    host: str,
    port: int = 993,
    ssl: bool = True,
) -> IMAPClient:
    """
    Log into an IMAP server and return the IMAP client object.

    Parameters:
        username: The IMAP username.
        password: The IMAP password.
        host: IMAP server host.
        port: IMAP server port.
        ssl: Use SSL for the IMAP connection.

    Returns:
        IMAPClient: An authenticated IMAP client instance.
    """
    imapObj = IMAPClient(host=host, port=port, ssl=ssl)
    imapObj.login(username=username, password=password)
    return imapObj


@Log.trace()
def get_folder_list(imapObj: IMAPClient) -> list[str]:
    """
    Retrieves a list of all folders from an IMAP server.

    Parameters:
        imapObj: The authenticated IMAP client object.

    Returns:
        list[str]: A list of folder names available on the IMAP server.
    """
    listBytes = imapObj.list_folders(directory="", pattern="*")
    listFolderName = [folder[2].decode("utf-8") if isinstance(folder[2], bytes) else folder[2] for folder in listBytes]
    return listFolderName


@Log.trace()
def get_email_list(
    imapObj: IMAPClient,
    folder: str = "INBOX",
    numToGet: int = 1,
    onlyUnread: bool = False,
    markAsRead: bool = False,
    charset: str | None = None,
) -> tuple[list[int], list[DictImapMailInfo], list[MailParser]]:
    """
    Retrieve a list of emails from the specified IMAP folder.

    Parameters:
        imapObj: An instance of the IMAPClient connected to the email server.
        folder: The name of the folder to fetch emails from.
        numToGet: The maximum number of emails to retrieve.
        onlyUnread: Whether to retrieve only unread emails.
        markAsRead: Whether to mark retrieved emails as read.
        charset: The charset to use for the search criteria.

    Returns:
        tuple[list[int],list[DictMailInfo],list[MailParser]]:
            A list of unique identifiers (UIDs) of the fetched emails.
            A list of basic information dictionaries for each email, adhering to the DictMailInfo structure.
            A list of MailParser objects representing the fetched emails.
    """
    imapObj.select_folder(folder=folder, readonly=not markAsRead)
    criteria = "UNSEEN" if onlyUnread else "ALL"
    listUid = imapObj.search(criteria=criteria, charset=charset)
    listUid = listUid[:numToGet]

    listEmail: list[MailParser] = []
    listBasicInfo: list[DictImapMailInfo] = []
    for UID in listUid:
        emailRaw = imapObj.fetch(messages=UID, data=["RFC822"])[UID][b"RFC822"]
        email: MailParser = parse_from_bytes(emailRaw)
        if markAsRead:
            imapObj.add_flags(messages=UID, flags=[R"\Seen"])
        listEmail.append(email)

        dictTemp = {
            "subject": email.subject or None,
            "from_": email.from_ or None,
            "to": email.to or None,
            "cc": email.cc or None,
            "bcc": email.bcc or None,
            "date": email.date or None,
            "received": email.received or None,
            "text_plain": email.text_plain or None,
            "text_html": email.text_html or None,
            "attachments": email.attachments or None,
            "headers": email.headers or None,
            "message_id": email.message_id or None,
            "to_domains": email.to_domains or None,
            "from_domains": email.from_domains or None,
            "cc_domains": email.cc_domains or None,
            "bcc_domains": email.bcc_domains or None,
            "delivered_to": email.delivered_to or None,
            "reply_to": email.reply_to or None,
            "body": email.body or None,
            "anomalies": email.anomalies or None,
            "mail": email.mail or None,
            "defects": email.defects or None,
            "defects_category": email.defects_category or None,
            "has_defects": email.has_defects or None,
        }

        if isinstance(dictTemp["date"], datetime):
            dictTemp["date"] = dictTemp["date"].strftime("%Y-%m-%d %H:%M:%S")
        listBasicInfo.append(dictTemp)  # type: ignore

    return (listUid, listBasicInfo, listEmail)


@Log.trace()
def search_email(
    imapObj: IMAPClient, folder: str = "INBOX", criteria: str = 'TEXT ""', charset: str | None = None
) -> tuple[list[int], list[DictImapMailInfo], list[MailParser]]:
    """
    Search for emails in the specified folder based on given criteria.

    Parameters:
        imapObj: An instance of the IMAPClient connected to the email server.
        folder: The name of the folder to search.
        criteria: The search criteria in IMAP format.
        charset: The charset to use for the search criteria.

    Returns:
        tuple[list[int],list[DictMailInfo],list[MailParser]]:
            A list of unique identifiers (UIDs) of the fetched emails.
            A list of basic information dictionaries for each email, adhering to the DictMailInfo structure.
            A list of MailParser objects representing the fetched emails.
    """
    imapObj.select_folder(folder=folder)
    listUid = imapObj.search(criteria=criteria, charset=charset)
    listEmail = []
    listBasicInfo: list[DictImapMailInfo] = []
    for UID in listUid:
        rawEmail = imapObj.fetch(messages=UID, data=["RFC822"])[UID][b"RFC822"]
        email: MailParser = parse_from_bytes(rawEmail)
        listEmail.append(email)
        dictTemp = {
            "subject": email.subject or None,
            "from_": email.from_ or None,
            "to": email.to or None,
            "cc": email.cc or None,
            "bcc": email.bcc or None,
            "date": email.date or None,
            "received": email.received or None,
            "text_plain": email.text_plain or None,
            "text_html": email.text_html or None,
            "attachments": email.attachments or None,
            "headers": email.headers or None,
            "message_id": email.message_id or None,
            "to_domains": email.to_domains or None,
            "from_domains": email.from_domains or None,
            "cc_domains": email.cc_domains or None,
            "bcc_domains": email.bcc_domains or None,
            "delivered_to": email.delivered_to or None,
            "reply_to": email.reply_to or None,
            "body": email.body or None,
            "anomalies": email.anomalies or None,
            "mail": email.mail or None,
            "defects": email.defects or None,
            "defects_category": email.defects_category or None,
            "has_defects": email.has_defects or None,
        }

        if isinstance(dictTemp["date"], datetime):
            dictTemp["date"] = dictTemp["date"].strftime("%Y-%m-%d %H:%M:%S")
        listBasicInfo.append(dictTemp)  # type: ignore

    return (listUid, listBasicInfo, listEmail)


@Log.trace()
def move_email(imapObj: IMAPClient, uid: int, folder: str) -> None:
    """
    Move an email by its uid.

    Parameters:
        imapObj: An instance of the IMAPClient connected to the email server.
        uid: The unique identifiers (UIDs) of the fetched emails.
        folder: The name of the folder to move.
    """
    imapObj.move(messages=uid, folder=folder)


@Log.trace()
def download_attachments(emailObj: MailParser, downloadPath: str) -> list[str]:
    """
    Download all attachments of an email.

    Parameters:
        emailObj: A MailParser objects.
        downloadPath: The folder to save download files.

    Returns:
        list[str]: A list contains the path of all attachments.
    """
    listFilePath: list[str] = []
    Path(downloadPath).mkdir(parents=True, exist_ok=True)
    for attachment in emailObj.attachments:
        strFilePath = Path(downloadPath).joinpath(attachment["filename"])

        try:
            # Decode the payload if it's base64 encoded
            if isinstance(attachment["payload"], str):
                payloadBytes = base64.b64decode(attachment["payload"])
            else:
                payloadBytes = attachment["payload"]

            with Path(strFilePath).open(mode="wb") as fileObj:
                fileObj.write(payloadBytes)

            listFilePath.append(str(strFilePath.absolute()))
        except Exception as e:
            raise MailError(f"Error downloading attachment {attachment['filename']}: {e}")

    return listFilePath


if __name__ == "__main__":

    # send_by_SMTP(
    #     user="",
    #     password="",
    #     to="",
    #     subject="test subject",
    #     content="<H1>123</H1>",
    #     host="smtp.qq.com",
    #     port=465,
    #     attachments=None,
    # )
    imapObj = IMAP_login(username="XXXX@qq.com", password="XXXX", host="imap.qq.com", port=993, ssl=True)
    # print(get_folder_list(imapObj))
    # log.debug_pretty(
    #     get_email_list(
    #         imapObj=imapObj,
    #         folder="其他文件夹/测试文件夹",
    #         numToGet=1,
    #         onlyUnread=False,
    #         markAsRead=False,
    #         charset=None,
    #     )
    # )
    # log.debug(search_email(imapObj=imapObj, folder="其他文件夹/测试文件夹", criteria='(FROM "XXXX@qq.com")', charset=None))
    listUid, _, listEmail = search_email(
        imapObj=imapObj, folder="INBOX", criteria='(TEXT "testOutlook3")', charset=None
    )
    print(listEmail)

    # move_email(imapObj=imapObj, uid=listUid[0], folder="INBOX")
    # print(download_attachments(emailObj=listEmail[0], downloadPath="./emailtest/"))
    move_email(imapObj=imapObj, uid=listUid[0], folder="其他文件夹/测试文件夹")
