"""A key vault for the tests: the "encryption" is a visible prefix, nothing touches the system."""

from wxclaude.core.errors import KeyVaultError

PREFIX = "fake-vault:"


class FakeVault:
    """Keeps a secret as ``fake-vault:<secret reversed>``.

    ``locked`` makes every decryption fail, as the DPAPI does for a blob written by another
    account.
    """

    def __init__(self, *, locked: bool = False) -> None:
        self.locked = locked

    def encrypt(self, secret: str) -> str:
        return PREFIX + secret[::-1]

    def decrypt(self, blob: str) -> str:
        if self.locked or not blob.startswith(PREFIX):
            raise KeyVaultError("Cannot decrypt the key.")
        return blob[len(PREFIX) :][::-1]
