"""The Windows DPAPI as a key vault: a real round trip, on Windows only."""

import sys

import pytest

from wxclaude.core.errors import KeyVaultError
from wxclaude.core.security.vault import DpapiVault

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(sys.platform != "win32", reason="the DPAPI is a Windows service"),
]

SECRET = "sk-test-0123456789 éà"


def test_a_secret_comes_back_as_it_was() -> None:
    vault = DpapiVault()
    assert vault.decrypt(vault.encrypt(SECRET)) == SECRET


def test_the_encrypted_text_does_not_hold_the_secret() -> None:
    blob = DpapiVault().encrypt(SECRET)
    assert "sk-test" not in blob
    assert blob.isascii()


def test_the_same_secret_is_not_encrypted_the_same_way_twice() -> None:
    vault = DpapiVault()
    assert vault.encrypt(SECRET) != vault.encrypt(SECRET)


def test_an_empty_secret_round_trips() -> None:
    vault = DpapiVault()
    assert vault.decrypt(vault.encrypt("")) == ""


@pytest.mark.parametrize("blob", ["", "not base64 !!", "AAAA", "dGhpcyBpcyBub3QgYSBibG9i"])
def test_a_text_that_is_not_an_encrypted_key_is_refused(blob: str) -> None:
    with pytest.raises(KeyVaultError):
        DpapiVault().decrypt(blob)
