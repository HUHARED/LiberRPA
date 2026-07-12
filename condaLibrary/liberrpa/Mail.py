# FileName: Mail.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictImapMailInfo, StrPath
from liberrpa.Common._Utils import normalize_attachment_paths, get_attachment_download_path
from liberrpa.Common._Exception import MailError
from imapclient import IMAPClient
from mailparser import parse_from_bytes, MailParser
from pathlib import Path
import base64
import yagmail
from datetime import datetime
from typing import Literal, Any, cast


@Log.trace()
def send_by_SMTP(
    user: str,
    password: str,
    to: str,
    subject: str,
    content: str,
    host: str,
    port: int = 465,
    attachments: StrPath | list[StrPath] | None = None,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    bodyFormat: Literal["text", "html"] = "text",
    ssl: bool = True,
    encoding: str = "utf-8",
) -> None:
    """
    Send an email via SMTP.

    Parameters:
        user: The SMTP username.
        password: The SMTP password.
        to: Recipient email address.
        subject: Email subject.
        content: Main email body content. Can be plain text or HTML.
        host: SMTP server host.
        port: SMTP server port.
        attachments: File path or list of file paths to attach. Accepts str or PathLike[str].
        cc: Email address or list of addresses for CC.
        bcc: Email address or list of addresses for BCC.
        bodyFormat: The format of the email body, either "text" or "html".
        ssl: Use SSL for the SMTP connection.
        encoding: Character encoding for the email.
    """
    attachmentsNormalized = normalize_attachment_paths(attachments)

    yag = yagmail.SMTP(user=user, password=password, host=host, port=port, smtp_ssl=ssl, encoding=encoding)

    match bodyFormat:
        case "text":
            yag.send(
                to=to,
                subject=subject,
                contents=content,
                attachments=attachmentsNormalized or None,
                cc=cc,
                bcc=bcc,
                prettify_html=False,
            )
        case "html":
            yag.send(
                to=to,
                subject=subject,
                contents=content,
                attachments=attachmentsNormalized or None,
                cc=cc,
                bcc=bcc,
                prettify_html=True,
            )
        case _:
            raise ValueError('The argument bodyFormat should be "text" or "html".')


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


def _none_if_empty(value: Any) -> Any:
    return None if value in ("", [], {}, ()) else value


def _mail_str(value: Any) -> str | None:
    return cast(str | None, _none_if_empty(value))


def _mail_bool(value: Any) -> bool | None:
    return cast(bool | None, _none_if_empty(value))


def _mail_address_list(value: Any) -> list[tuple[str, str]] | None:
    return cast(list[tuple[str, str]] | None, _none_if_empty(value))


def _mail_list_dict(value: Any) -> list[dict[str, Any]] | None:
    return cast(list[dict[str, Any]] | None, _none_if_empty(value))


def _mail_list_str(value: Any) -> list[str] | None:
    return cast(list[str] | None, _none_if_empty(value))


def _mail_dict_str(value: Any) -> dict[str, str] | None:
    return cast(dict[str, str] | None, _none_if_empty(value))


def _mail_dict_any(value: Any) -> dict[str, Any] | None:
    return cast(dict[str, Any] | None, _none_if_empty(value))


def _mail_str_or_list_str(value: Any) -> str | list[str] | None:
    return cast(str | list[str] | None, _none_if_empty(value))


def _mail_list_any(value: Any) -> list[Any] | None:
    return cast(list[Any] | None, _none_if_empty(value))


def _mail_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return _mail_str(value)


def _get_basic_mail_info(email: MailParser) -> DictImapMailInfo:
    dictInfo: DictImapMailInfo = {
        "subject": _mail_str(email.subject),
        "from_": _mail_address_list(email.from_),
        "to": _mail_address_list(email.to),
        "cc": _mail_address_list(email.cc),
        "bcc": _mail_address_list(email.bcc),
        "date": _mail_date(email.date),
        "received": _mail_list_dict(email.received),
        "text_plain": _mail_list_str(email.text_plain),
        "text_html": _mail_list_str(email.text_html),
        "attachments": _mail_list_dict(email.attachments),
        "headers": _mail_dict_str(email.headers),
        "message_id": _mail_str(email.message_id),
        "to_domains": _mail_str_or_list_str(email.to_domains),
        "from_domains": _mail_str_or_list_str(email.from_domains),
        "cc_domains": _mail_str_or_list_str(email.cc_domains),
        "bcc_domains": _mail_str_or_list_str(email.bcc_domains),
        "delivered_to": _mail_list_str(email.delivered_to),
        "reply_to": _mail_list_str(email.reply_to),
        "body": _mail_str(email.body),
        "anomalies": _mail_str(email.anomalies),
        "mail": _mail_dict_any(email.mail),
        "defects": _mail_list_any(email.defects),
        "defects_category": _mail_str(email.defects_category),
        "has_defects": _mail_bool(email.has_defects),
    }

    return dictInfo


@Log.trace()
def get_email_list(
    imapObj: IMAPClient,
    folder: str = "INBOX",
    limit: int = 1,
    onlyUnread: bool = False,
    markAsRead: bool = False,
    charset: str | None = None,
) -> tuple[list[int], list[DictImapMailInfo], list[MailParser]]:
    """
    Retrieve a list of emails from the specified IMAP folder.

    Parameters:
        imapObj: An instance of the IMAPClient connected to the email server.
        folder: The name of the folder to fetch emails from.
        limit: The maximum number of emails to retrieve.
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
    listUid = listUid[:limit]

    listEmail: list[MailParser] = []
    listBasicInfo: list[DictImapMailInfo] = []
    for UID in listUid:
        emailRaw = imapObj.fetch(messages=UID, data=["RFC822"])[UID][b"RFC822"]
        email: MailParser = parse_from_bytes(emailRaw)
        if markAsRead:
            imapObj.add_flags(messages=UID, flags=[R"\Seen"])
        listEmail.append(email)

        listBasicInfo.append(_get_basic_mail_info(email=email))

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

        listBasicInfo.append(_get_basic_mail_info(email=email))

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
def download_attachments(
    emailObj: MailParser,
    downloadPath: StrPath,
) -> list[str]:
    """
    Download all attachments of an email.

    Parameters:
        emailObj: A MailParser object.
        downloadPath: The folder to save downloaded files. Accepts str or PathLike[str].

    Returns:
        list[str]: Absolute paths of the downloaded attachments.
    """

    pathDownloadRoot = Path(downloadPath)
    pathDownloadRoot.mkdir(parents=True, exist_ok=True)

    listFilePath: list[str] = []

    for attachment in emailObj.attachments:
        attachmentFileName = attachment.get("filename")

        try:
            if not isinstance(attachmentFileName, str):
                raise ValueError(f"Attachment filename must be a string, got {type(attachmentFileName).__name__}.")

            pathFile = get_attachment_download_path(
                downloadPath=pathDownloadRoot,
                attachmentFileName=attachmentFileName,
            )

            if pathFile.name != attachmentFileName:
                Log.warning(
                    f"Attachment filename changed from {attachmentFileName!r} "
                    f"to {pathFile.name!r} to keep it inside the download "
                    f"folder or avoid overwriting an existing file."
                )

            payload = attachment["payload"]

            if isinstance(payload, str):
                payloadBytes = base64.b64decode(payload)
            else:
                payloadBytes = payload

            # Exclusive creation prevents an unexpected concurrent overwrite.
            with pathFile.open(mode="xb") as fileObj:
                fileObj.write(payloadBytes)

            listFilePath.append(str(pathFile))

        except Exception as e:
            raise MailError(f"Error downloading attachment {attachmentFileName!r}: {e}") from e

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
    #         limit=1,
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
