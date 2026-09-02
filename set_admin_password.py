"""
set_admin_password.py — set/reset the admin password on an EXISTING
install, without a forced change on next login, and without ever
writing the plaintext password into a committed file.

This is the supported way to do what a hardcoded password in app.py
would otherwise do, minus the downsides: nothing secret ends up in
source control, and the account still goes through the same hashing
(werkzeug) and password-history tracking as a normal change.

Usage:
    python set_admin_password.py <username> "<new password>"

If you omit the password argument, you'll be prompted for it
(hidden input) instead of it appearing in your shell history.
"""
import sys
import getpass
import datetime
from werkzeug.security import generate_password_hash

import db


def main():
    if len(sys.argv) < 2:
        print("Usage: python set_admin_password.py <username> [new password]")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else getpass.getpass("New password: ")

    if len(password.strip()) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    db.init_db()  # make sure tables/columns exist
    admin_user = db.find_admin_by_username_or_email(username)
    if not admin_user:
        print(f"No admin account named '{username}' exists yet.")
        sys.exit(1)

    db.set_password(admin_user["username"], password)
    print(f"Password updated for '{admin_user['username']}'. You can log straight into /admin with it.")


if __name__ == "__main__":
    main()
