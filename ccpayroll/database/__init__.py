"""
Database management module for Creative Closets Payroll
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
import os
from flask import current_app, g

# Thread-local storage for database connections
db_local = threading.local()
db_connections = {}  # Track connections for monitoring

@contextmanager
def get_db():
    """Context manager for getting database connection"""
    thread_id = threading.get_ident()
    
    if not hasattr(db_local, 'connection'):
        database_path = os.path.join(current_app.config['DATA_FOLDER'], 'payroll.db')
        db_local.connection = sqlite3.connect(database_path)
        db_local.connection.row_factory = sqlite3.Row
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
        
        # Check if employees table exists and if we need to migrate
        cursor.execute("PRAGMA table_info(employees)")
        columns = cursor.fetchall()
        column_names = [column['name'] for column in columns]
        
        if not columns:
            # Create employees table if it doesn't exist
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
        elif 'installer_role' in column_names and 'position' not in column_names:
            # Migrate from installer_role to position
            current_app.logger.info("Migrating employees table from installer_role to position")
            # Create new table with updated schema
            cursor.execute('''
            CREATE TABLE employees_new (
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
            # Copy data from old table to new table
            cursor.execute('''
            INSERT INTO employees_new (id, name, rate, install_crew, position)
            SELECT id, name, rate, install_crew, installer_role FROM employees
            ''')
            # Drop old table
            cursor.execute('DROP TABLE employees')
            # Rename new table to employees
            cursor.execute('ALTER TABLE employees_new RENAME TO employees')
            current_app.logger.info("Migration complete")
        elif 'pay_type' not in column_names:
            # Add pay_type, salary, and commission_rate columns if they don't exist
            current_app.logger.info("Adding pay_type, salary, and commission_rate columns to employees table")
            cursor.execute('ALTER TABLE employees ADD COLUMN pay_type TEXT DEFAULT "hourly"')
            cursor.execute('ALTER TABLE employees ADD COLUMN salary REAL')
            cursor.execute('ALTER TABLE employees ADD COLUMN commission_rate REAL')
            current_app.logger.info("Columns added successfully")
        
        # Create timesheet table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timesheet_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id TEXT NOT NULL,
            employee_name TEXT NOT NULL,
            day TEXT NOT NULL,
            hours TEXT,
            pay TEXT,
            project_name TEXT,
            install_days TEXT,
            install TEXT,
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
        # Migrate any existing JSON data to SQLite
        from .migration import migrate_json_to_db
        migrate_json_to_db() 