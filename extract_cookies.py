"""Extract LinkedIn cookies (JSESSIONID, li_at) from Brave browser on macOS."""

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

BRAVE_COOKIE_DB = os.path.expanduser(
    "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies"
)
KEYCHAIN_SERVICE = "Brave Safe Storage"
SALT = b"saltysalt"
IV = b" " * 16
ITERATIONS = 1003
KEY_LENGTH = 16


def get_encryption_key():
    """Get the Brave cookie encryption key from macOS Keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", KEYCHAIN_SERVICE],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("Failed to get Brave encryption key from Keychain.", file=sys.stderr)
        sys.exit(1)
    password = result.stdout.strip().encode("utf-8")
    return hashlib.pbkdf2_hmac("sha1", password, SALT, ITERATIONS, dklen=KEY_LENGTH)


def decrypt_cookie(encrypted_value, key, db_version):
    """Decrypt a Chromium cookie value."""
    if encrypted_value[:3] == b"v10":
        encrypted_value = encrypted_value[3:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(IV))
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypted_value) + decryptor.finalize()
    # DB version >= 24 prepends a 32-byte SHA256 domain hash
    if db_version >= 24:
        decrypted = decrypted[32:]
    unpadder = padding.PKCS7(128).unpadder()
    return (unpadder.update(decrypted) + unpadder.finalize()).decode("utf-8")


def extract_linkedin_cookies():
    """Extract JSESSIONID and li_at from Brave's cookie database."""
    if not os.path.exists(BRAVE_COOKIE_DB):
        print("Brave cookie database not found.", file=sys.stderr)
        sys.exit(1)

    key = get_encryption_key()

    # Copy DB to avoid locking issues with open browser
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy2(BRAVE_COOKIE_DB, tmp)
    os.chmod(tmp, 0o600)

    try:
        conn = sqlite3.connect(tmp)
        db_version = int(conn.execute(
            "SELECT value FROM meta WHERE key = 'version'"
        ).fetchone()[0])
        cookies = {}
        for name in ("JSESSIONID", "li_at"):
            row = conn.execute(
                "SELECT encrypted_value FROM cookies "
                "WHERE host_key IN ('.www.linkedin.com', '.linkedin.com') AND name = ?",
                (name,),
            ).fetchone()
            if row and row[0]:
                cookies[name] = decrypt_cookie(row[0], key, db_version)
        conn.close()
    finally:
        os.unlink(tmp)

    return cookies


def main():
    cookies = extract_linkedin_cookies()

    if not cookies.get("JSESSIONID") or not cookies.get("li_at"):
        missing = [k for k in ("JSESSIONID", "li_at") if k not in cookies]
        print(f"Missing cookies: {', '.join(missing)}", file=sys.stderr)
        print("Make sure you're logged into LinkedIn in Brave.", file=sys.stderr)
        sys.exit(1)

    jsessionid = cookies["JSESSIONID"].strip('"')
    li_at = cookies["li_at"]

    if "--env" in sys.argv:
        print(f'LINKEDIN_JSESSIONID="{jsessionid}"')
        print(f'LINKEDIN_LI_AT="{li_at}"')
    else:
        print(f"JSESSIONID: {cookies['JSESSIONID']}")
        print(f"li_at:      {li_at[:20]}...{li_at[-10:]}")

        clip = f'JSESSIONID="{jsessionid}"\nli_at={li_at}'
        subprocess.run(["pbcopy"], input=clip.encode(), check=True)
        print("\nCopied to clipboard.")


if __name__ == "__main__":
    main()
