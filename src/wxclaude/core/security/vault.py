"""Keeping the key of a provider encrypted (``docs/security.md``, "The key").

``KeyVault`` turns a secret into a text that can be written in ``providers.json`` and back.
``DpapiVault`` does it with the Windows DPAPI: the text can be decrypted only by the same Windows
account on the same computer. That protects against a copied disk, a backup or another user; it
cannot protect against a program running as the user, which no local scheme does.
"""

import base64
import ctypes
import sys
from ctypes import wintypes
from typing import Protocol

from wxclaude.core.errors import KeyVaultError

_UI_FORBIDDEN = 0x1  # CRYPTPROTECT_UI_FORBIDDEN: never show a dialog
_DESCRIPTION = "WxClaude provider key"
_ENTROPY = b"WxClaude provider key v1"  # a program that does not know it does not decrypt by chance


class KeyVault(Protocol):
    """What the providers need to keep a key."""

    def encrypt(self, secret: str) -> str:
        """The secret as a text safe to write in a JSON file; raises ``KeyVaultError``."""
        ...

    def decrypt(self, blob: str) -> str:
        """The secret in ``blob``; raises ``KeyVaultError`` if it cannot be read here."""
        ...


class _DataBlob(ctypes.Structure):
    _fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char)))


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    """A DATA_BLOB over ``data``; the buffer is returned too so that it stays alive."""
    buffer = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _take(blob: _DataBlob) -> bytes:
    """The bytes the system allocated in ``blob``, which are then released."""
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


class DpapiVault:
    """The Windows DPAPI, bound to the account of the user."""

    def encrypt(self, secret: str) -> str:
        if sys.platform != "win32":
            raise KeyVaultError("The Windows DPAPI is not available on this system.")
        source, keep_source = _blob(secret.encode("utf-8"))
        entropy, keep_entropy = _blob(_ENTROPY)
        result = _DataBlob()
        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(source),
            _DESCRIPTION,
            ctypes.byref(entropy),
            None,
            None,
            _UI_FORBIDDEN,
            ctypes.byref(result),
        ):
            raise KeyVaultError(f"The key could not be encrypted: {ctypes.WinError()}")
        del keep_source, keep_entropy
        return base64.b64encode(_take(result)).decode("ascii")

    def decrypt(self, blob: str) -> str:
        if sys.platform != "win32":
            raise KeyVaultError("The Windows DPAPI is not available on this system.")
        try:
            data = base64.b64decode(blob.encode("ascii"), validate=True)
        except ValueError as error:
            raise KeyVaultError(f"The encrypted key is not valid: {error}") from error
        source, keep_source = _blob(data)
        entropy, keep_entropy = _blob(_ENTROPY)
        result = _DataBlob()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            ctypes.byref(entropy),
            None,
            None,
            _UI_FORBIDDEN,
            ctypes.byref(result),
        ):
            raise KeyVaultError(f"The key could not be decrypted: {ctypes.WinError()}")
        del keep_source, keep_entropy
        return _take(result).decode("utf-8", errors="replace")
