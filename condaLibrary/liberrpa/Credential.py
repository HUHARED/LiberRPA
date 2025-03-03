# FileName: Credential.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import win32cred
from typing import Literal, TypedDict

TypeOfCredential = Literal["GENERIC", "DOMAIN_PASSWORD", "DOMAIN_CERTIFICATE", "DOMAIN_VISIBLE_PASSWORD"]

listCredential: list[str] = list(TypeOfCredential.__args__)


class DictCredential(TypedDict):
    username: str
    password: str


def _check_type(credentialType: TypeOfCredential = "GENERIC") -> int:
    match credentialType:
        case "GENERIC":
            Type = win32cred.CRED_TYPE_GENERIC
        case "DOMAIN_PASSWORD":
            Type = win32cred.CRED_TYPE_DOMAIN_PASSWORD
        case "DOMAIN_CERTIFICATE":
            Type = win32cred.CRED_TYPE_DOMAIN_CERTIFICATE
        case "DOMAIN_VISIBLE_PASSWORD":
            Type = win32cred.CRED_TYPE_DOMAIN_VISIBLE_PASSWORD
        case _:
            raise ValueError(f"The argument credentialType should be one of {listCredential}")
    return Type


@Log.trace()
def get_windows_credential(
    credentialType: TypeOfCredential = "GENERIC",
    targetName: str = "",
) -> DictCredential:
    """
    Reads a credential from the Windows Credential Manager.

    Parameters:
        credentialType: The type of the credential to be read.
        targetName: The name used to identify the credential.

    Returns:
        DictCredential: A dictionary containing the 'username' and 'password' from the credential.
    """

    if not targetName:
        raise ValueError("targetName cannot be empty.")

    Type = _check_type(credentialType)

    try:
        dictCredential = win32cred.CredRead(Type=Type, TargetName=targetName)
        return {
            "username": dictCredential["UserName"],
            "password": dictCredential["CredentialBlob"].decode("utf-16-le"),
        }
    except Exception as e:
        raise ValueError(f"Failed to retrieve credential for target '{targetName}': {e}")


@Log.trace()
def write_windows_credential(
    credentialType: TypeOfCredential = "GENERIC",
    targetName="",
    userName="",
    credentialBlob="",
    persist: Literal["SESSION", "LOCAL_MACHINE", "ENTERPRISE"] = "LOCAL_MACHINE",
) -> None:
    """
    Writes a credential to the Windows Credential Manager.

    Parameters:
        credentialType: The type of the credential to be stored. Options:
            'GENERIC': General-purpose credentials (most common).
            'DOMAIN_PASSWORD': Standard domain password (used for domain authentication).
            'DOMAIN_CERTIFICATE': Credentials backed by a certificate.
            'DOMAIN_VISIBLE_PASSWORD': A domain password that is visible and retrievable.
        targetName: The name used to identify the credential.
        userName: The username associated with the credential.
        credentialBlob: The secret (password or data) to be stored.
        persist: Determines how long the credential persists. Options:
            'SESSION': The credential persists for the current logon session only.
            'LOCAL_MACHINE': The credential persists on the local machine (default).
            'ENTERPRISE': The credential persists across the enterprise (domain-wide persistence).
    """
    if not targetName:
        raise ValueError("targetName cannot be empty.")
    if not userName:
        raise ValueError("userName cannot be empty.")
    if not credentialBlob:
        raise ValueError("credentialBlob cannot be empty.")

    Type = _check_type(credentialType)

    match persist:
        case "SESSION":
            Persist = win32cred.CRED_PERSIST_SESSION
        case "LOCAL_MACHINE":
            Persist = win32cred.CRED_PERSIST_LOCAL_MACHINE
        case "ENTERPRISE":
            Persist = win32cred.CRED_PERSIST_ENTERPRISE
        case _:
            listTemp = ["SESSION", "LOCAL_MACHINE", "ENTERPRISE"]
            raise ValueError(f"The argument persist should be one of {listTemp}")

    win32cred.CredWrite(
        Credential=dict(
            Type=Type,
            TargetName=targetName,
            UserName=userName,
            CredentialBlob=credentialBlob,
            Persist=Persist,
        ),
        Flags=0,
    )


@Log.trace()
def delete_windows_credential(
    credentialType: TypeOfCredential = "GENERIC",
    targetName: str = "",
) -> None:
    """
    Delete a credential from the Windows Credential Manager.

    Parameters:
        credentialType: The type of the credential to be deleted.
        targetName: The name used to identify the credential.
    """

    if not targetName:
        raise ValueError("targetName cannot be empty.")

    Type = _check_type(credentialType)

    try:
        win32cred.CredDelete(Type=Type, TargetName=targetName)
    except Exception as e:
        raise ValueError(f"Failed to delete credential for target '{targetName}': {e}")


if __name__ == "__main__":
    write_windows_credential(
        credentialType="GENERIC", targetName="test1", userName="test2", credentialBlob="test4", persist="LOCAL_MACHINE"
    )
    # print(get_windows_credential(credentialType="GENERIC", targetName="test13"))
    # delete_windows_credential(credentialType="GENERIC",targetName="test1")
