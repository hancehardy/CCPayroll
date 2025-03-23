"""
PostgreSQL database adapter for Creative Closets Payroll application

This module provides PostgreSQL database connection functionality as a drop-in
replacement for the SQLite database adapter.

Usage:
    # In app.py or __init__.py
    from ccpayroll.database import init_app
    # ... 
    init_app(app, adapter='postgresql')  # Use PostgreSQL

    # Or to explicitly choose PostgreSQL
    from ccpayroll.database.pg_adapter import init_app as init_pg_app
    init_pg_app(app)
"""

import os
import threading
import logging
from contextlib import contextmanager
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import current_app, g

# Thread-local storage for database connections
db_local = threading.local()
db_connections = {}  # Track connections for monitoring

@contextmanager
def get_db():
    """Context manager for getting PostgreSQL database connection
    
    This is designed to be a drop-in replacement for the SQLite version.
    """
    thread_id = threading.get_ident()
    
    if not hasattr(db_local, 'connection'):
        # Get DATABASE_URL from environment
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            current_app.logger.error("DATABASE_URL environment variable not set")
            raise Exception("DATABASE_URL environment variable not set")
        
        try:
            db_local.connection = psycopg2.connect(database_url)
            db_connections[thread_id] = {
                'created_at': datetime.now(),
                'last_used': datetime.now()
            }
            current_app.logger.info(f"New PostgreSQL DB connection created for thread {thread_id}")
        except psycopg2.Error as e:
            current_app.logger.error(f"PostgreSQL connection error: {e}")
            raise
    else:
        # Update last used time
        if thread_id in db_connections:
            db_connections[thread_id]['last_used'] = datetime.now()
    
    try:
        # Create a cursor using the RealDictCursor to emulate SQLite's Row factory
        cursor = db_local.connection.cursor(cursor_factory=RealDictCursor)
        # Make a simple connection check query to ensure the connection is alive
        cursor.execute("SELECT 1")
        cursor.close()
        
        yield db_local.connection
    except psycopg2.Error as e:
        db_local.connection.rollback()
        current_app.logger.error(f"PostgreSQL database error in thread {thread_id}: {str(e)}")
        
        # Try to reconnect on connection errors
        try:
            db_local.connection.close()
            del db_local.connection
            # Reconnect
            database_url = os.getenv('DATABASE_URL')
            db_local.connection = psycopg2.connect(database_url)
            current_app.logger.info(f"Reconnected to PostgreSQL for thread {thread_id}")
            yield db_local.connection
        except psycopg2.Error as reconnect_error:
            current_app.logger.error(f"PostgreSQL reconnection failed: {reconnect_error}")
            raise
    finally:
        # Keep connection open for this thread's lifetime
        pass

def close_db():
    """Close database connection if it exists"""
    thread_id = threading.get_ident()
    
    if hasattr(db_local, 'connection'):
        db_local.connection.close()
        if thread_id in db_connections:
            del db_connections[thread_id]
        del db_local.connection
        current_app.logger.info(f"Closed PostgreSQL DB connection for thread {thread_id}")

def monitor_db_connections():
    """Log information about current database connections"""
    now = datetime.now()
    for thread_id, info in list(db_connections.items()):
        age = (now - info['created_at']).total_seconds()
        idle_time = (now - info['last_used']).total_seconds()
        
        if idle_time > 300:  # 5 minutes idle
            current_app.logger.warning(f"Thread {thread_id} has idle PostgreSQL DB connection for {idle_time:.1f} seconds")
        
        if age > 3600:  # 1 hour old
            current_app.logger.info(f"Thread {thread_id} has PostgreSQL DB connection open for {age:.1f} seconds")

def init_db():
    """Initialize the database schema
    
    This function is intentionally empty as we assume the schema is already created
    by the migration script before switching to PostgreSQL.
    """
    pass

def init_app(app):
    """Initialize database connection for the Flask app
    
    This is a PostgreSQL-specific version of the init_app function.
    """
    # Add before_request function to periodically monitor connections
    @app.before_request
    def before_request():
        """Run before each request"""
        # Random chance to monitor connections (1%)
        import random
        if random.random() < 0.01:
            monitor_db_connections()
    
    # Add teardown function to close connections
    @app.teardown_appcontext
    def teardown_db(exception):
        """Close database connection at the end of the request"""
        close_db()
    
    # No need to initialize the database as it's already created by migration script
    
    # Make sure we have the required environment variable
    if not os.getenv('DATABASE_URL'):
        app.logger.warning("DATABASE_URL environment variable not set. PostgreSQL adapter will not work.")

# Helper function to quote identifiers safely
def pg_identifier(identifier):
    """Quote an identifier (table name, column name) for PostgreSQL"""
    return f'"{identifier}"' 