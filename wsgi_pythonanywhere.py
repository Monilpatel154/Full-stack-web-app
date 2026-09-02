"""
PythonAnywhere WSGI configuration file for the LADLI website.

Where this goes:
  On the "Web" tab of your PythonAnywhere dashboard, there is a link to
  "WSGI configuration file" (something like
  /var/www/yourusername_pythonanywhere_com_wsgi.py). Open it and replace
  its entire contents with this file, then edit the two lines marked
  CHANGE ME below. Click "Reload" on the Web tab afterwards.
"""

import sys
import os

# ---------------------------------------------------------------------
# Set PYTHONANYWHERE_PROJECT_HOME in the WSGI file or the environment to
# the folder that directly contains app.py. Example:
#   /home/yourusername/ladli
# ---------------------------------------------------------------------
project_home = os.environ.get('PYTHONANYWHERE_PROJECT_HOME', '/home/yourusername/ladli')

if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ---------------------------------------------------------------------
# Admin credentials: leave these unset here. app.py will read
# ADMIN_USERNAME / ADMIN_PASSWORD from your project's .env file (see
# .env.example) if present. If you don't set ADMIN_PASSWORD anywhere,
# a strong one-time password is generated automatically on first run
# and printed to this app's error log the first time it starts — open
# the "Log files" section on your Web tab to read it, then log in and
# set your own password immediately (you'll be required to before you
# can do anything else in the admin portal).
# ---------------------------------------------------------------------

from app import app as application  # noqa: E402
