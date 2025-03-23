"""
Database management module for Creative Closets Payroll
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
import os
from flask import current_app, g
import logging

# Actual implementations imported based on adapter choice
from .sqlite_adapter import get_db as get_sqlite_db
from .sqlite_adapter import close_db as close_sqlite_db
from .sqlite_adapter import monitor_db_connections as monitor_sqlite_connections
from .sqlite_adapter import init_db as init_sqlite_db
from .sqlite_adapter import init_app as init_sqlite_app

try:
    from .pg_adapter import get_db as get_pg_db
    from .pg_adapter import close_db as close_pg_db
    from .pg_adapter import monitor_db_connections as monitor_pg_connections
    from .pg_adapter import init_db as init_pg_db
    from .pg_adapter import init_app as init_pg_app
    _has_pg_adapter = True
except ImportError:
    _has_pg_adapter = False
    
# Global to store which adapter is being used
_adapter = 'sqlite'

# Proxied functions that delegate to the chosen adapter
def get_db():
    """Context manager for getting database connection"""
    if _adapter == 'postgresql':
        if not _has_pg_adapter:
            raise ImportError("PostgreSQL adapter not available. Make sure psycopg2 is installed.")
        return get_pg_db()
    else:
        return get_sqlite_db()

def close_db():
    """Close database connection if it exists"""
    if _adapter == 'postgresql':
        if _has_pg_adapter:
            return close_pg_db()
    else:
        return close_sqlite_db()

def monitor_db_connections():
    """Log information about current database connections"""
    if _adapter == 'postgresql':
        if _has_pg_adapter:
            return monitor_pg_connections()
    else:
        return monitor_sqlite_connections()

def init_db():
    """Initialize the database schema"""
    if _adapter == 'postgresql':
        if _has_pg_adapter:
            return init_pg_db()
    else:
        return init_sqlite_db()

def init_app(app, adapter='sqlite'):
    """Initialize database connection and schema for the Flask app
    
    Args:
        app: Flask application instance
        adapter: Database adapter to use ('sqlite' or 'postgresql')
    """
    global _adapter
    
    # Determine which adapter to use
    if adapter == 'postgresql':
        if not _has_pg_adapter:
            app.logger.warning("PostgreSQL adapter requested but not available. Using SQLite instead.")
            _adapter = 'sqlite'
            return init_sqlite_app(app)
        else:
            app.logger.info("Using PostgreSQL database adapter")
            _adapter = 'postgresql'
            
            # Check if DATABASE_URL is set
            if not os.getenv('DATABASE_URL'):
                app.logger.error("DATABASE_URL environment variable not set. PostgreSQL adapter will not work.")
                
            return init_pg_app(app)
    else:
        app.logger.info("Using SQLite database adapter")
        _adapter = 'sqlite'
        return init_sqlite_app(app)
        
def get_adapter_name():
    """Return the name of the current adapter"""
    return _adapter 