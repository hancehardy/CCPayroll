"""
Database management module for Creative Closets Payroll
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import threading
import os
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv
from flask import current_app, g

# Load environment variables from .env file
load_dotenv()

# Thread-local storage for database connections
db_local = threading.local()
db_connections = {}  # Track connections for monitoring

@contextmanager
def get_db():
    """Context manager for getting database connection"""
    thread_id = threading.get_ident()
    
    if not hasattr(db_local, 'connection'):
        # PostgreSQL connection parameters
        host = os.environ.get('PG_HOST', 'localhost')
        port = os.environ.get('PG_PORT', '5432')
        user = os.environ.get('PG_USER', 'postgres')
        password = os.environ.get('PG_PASSWORD', 'postgres')
        db_name = os.environ.get('PG_DB', 'ccpayroll')
        
        # Connect to PostgreSQL
        db_local.connection = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=db_name,
            cursor_factory=RealDictCursor
        )
        db_connections[thread_id] = {
            'created_at': datetime.now(),
            'last_used': datetime.now()
        }
        current_app.logger.info(f"New DB connection created for thread {thread_id}")
    else:
        # Update last used time
        if thread_id in db_connections:
            db_connections[thread_id]['last_used'] = datetime.now()
    
    try:
        yield db_local.connection
    except Exception as e:
        db_local.connection.rollback()
        current_app.logger.error(f"Database error in thread {thread_id}: {str(e)}")
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
        current_app.logger.info(f"Closed DB connection for thread {thread_id}")

def monitor_db_connections():
    """Log information about current database connections"""
    now = datetime.now()
    for thread_id, info in list(db_connections.items()):
        age = (now - info['created_at']).total_seconds()
        idle_time = (now - info['last_used']).total_seconds()
        
        if idle_time > 300:  # 5 minutes idle
            current_app.logger.warning(f"Thread {thread_id} has idle DB connection for {idle_time:.1f} seconds")
        
        if age > 3600:  # 1 hour old
            current_app.logger.info(f"Thread {thread_id} has DB connection open for {age:.1f} seconds")

def init_db():
    """Initialize the database schema"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create pay_periods table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pay_periods (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        )
        ''')
        
        # Create employees table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            rate REAL,
            install_crew INTEGER DEFAULT 0,
            position TEXT,
            pay_type TEXT DEFAULT 'hourly',
            salary REAL,
            commission_rate REAL
        )
        ''')
        
        # Create timesheet table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timesheet_entries (
            id SERIAL PRIMARY KEY,
            period_id TEXT NOT NULL,
            employee_name TEXT NOT NULL,
            day TEXT NOT NULL,
            hours TEXT,
            pay TEXT,
            project_name TEXT,
            install_days TEXT,
            install TEXT,
            regular_hours REAL DEFAULT 0,
            overtime_hours REAL DEFAULT 0,
            job_name TEXT,
            notes TEXT,
            FOREIGN KEY (period_id) REFERENCES pay_periods(id),
            UNIQUE (period_id, employee_name, day)
        )
        ''')
        
        conn.commit()

def init_app(app):
    """Initialize database connection and schema for the Flask app"""
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
    
    # Initialize database
    with app.app_context():
        init_db()
        # Migrate any existing JSON data to database
        from .migration import migrate_json_to_db
        migrate_json_to_db() 