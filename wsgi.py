"""
WSGI entry point for the CCPayroll application.
This file is used by Gunicorn to start the application.
"""

from app import app as application

# This allows the app to be run with gunicorn
if __name__ == "__main__":
    application.run() 