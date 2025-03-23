"""
Database management module for Creative Closets Payroll
"""

import os
import sqlite3
import threading
import logging
from contextlib import contextmanager
from datetime import datetime
import re
from flask import current_app, g

# Thread-local storage for database connections
db_local = threading.local()
db_connections = {}  # Track connections for monitoring

# Configure logging
logger = logging.getLogger('payroll.database')

def get_db_url():
    """Get the database URL from environment variables"""
    return os.environ.get('DATABASE_URL', 'sqlite:///data/payroll.db')

def is_postgres_url(url):
    """Check if the database URL is for PostgreSQL"""
    return url.startswith('postgres:') or url.startswith('postgresql:')

@contextmanager
def get_db():
    """Context manager for getting database connection"""
    thread_id = threading.get_ident()
    db_url = get_db_url()
    
    if not hasattr(db_local, 'connection'):
        if is_postgres_url(db_url):
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                
                # Handle old-style heroku postgres URLs if necessary
                if db_url.startswith('postgres://'):
                    db_url = db_url.replace('postgres://', 'postgresql://', 1)
                
                db_local.connection = psycopg2.connect(db_url)
                db_local.connection_type = 'postgres'
                logger.info(f"New PostgreSQL connection created for thread {thread_id}")
            except ImportError:
                logger.error("Psycopg2 not installed. Cannot connect to PostgreSQL.")
                raise
        else:
            # Extract path from sqlite URL
            match = re.match(r'sqlite:///(.+)', db_url)
            if match:
                db_path = match.group(1)
            else:
                db_path = db_url.replace('sqlite:///', '')
                
            db_local.connection = sqlite3.connect(db_path)
            db_local.connection.row_factory = sqlite3.Row
            db_local.connection_type = 'sqlite'
            logger.info(f"New SQLite connection created for thread {thread_id}")
        
        db_connections[thread_id] = {
            'created_at': datetime.now(),
            'last_used': datetime.now(),
            'type': db_local.connection_type
        }
    else:
        # Update last used time
        if thread_id in db_connections:
            db_connections[thread_id]['last_used'] = datetime.now()
    
    try:
        yield db_local.connection
    except Exception as e:
        db_local.connection.rollback()
        logger.error(f"Database error in thread {thread_id}: {str(e)}")
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
        logger.info(f"Closed DB connection for thread {thread_id}")

def monitor_db_connections():
    """Log information about current database connections"""
    now = datetime.now()
    for thread_id, info in list(db_connections.items()):
        age = (now - info['created_at']).total_seconds()
        idle_time = (now - info['last_used']).total_seconds()
        
        if idle_time > 300:  # 5 minutes idle
            logger.warning(f"Thread {thread_id} has idle DB connection for {idle_time:.1f} seconds")
        
        if age > 3600:  # 1 hour old
            logger.info(f"Thread {thread_id} has DB connection open for {age:.1f} seconds")

def init_db():
    """Initialize the database with required tables"""
    with get_db() as conn:
        db_type = getattr(db_local, 'connection_type', 'sqlite')
        cursor = conn.cursor()
        
        if db_type == 'postgres':
            # PostgreSQL syntax
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pay_periods (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL
            )
            ''')
            
            # Check if employees table exists
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'employees')")
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
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
                regular_hours REAL,
                overtime_hours REAL,
                job_name TEXT,
                notes TEXT,
                FOREIGN KEY (period_id) REFERENCES pay_periods(id),
                UNIQUE (period_id, employee_name, day)
            )
            ''')
        else:
            # SQLite syntax
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pay_periods (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL
            )
            ''')
            
            # Check if employees table exists
            cursor.execute("PRAGMA table_info(employees)")
            columns = cursor.fetchall()
            column_names = [column['name'] for column in columns] if columns else []
            
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
                logger.info("Migrating employees table from installer_role to position")
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
                logger.info("Migration complete")
            elif 'pay_type' not in column_names:
                # Add pay_type, salary, and commission_rate columns if they don't exist
                logger.info("Adding pay_type, salary, and commission_rate columns to employees table")
                cursor.execute('ALTER TABLE employees ADD COLUMN pay_type TEXT DEFAULT "hourly"')
                cursor.execute('ALTER TABLE employees ADD COLUMN salary REAL')
                cursor.execute('ALTER TABLE employees ADD COLUMN commission_rate REAL')
                logger.info("Columns added successfully")
            
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
                regular_hours REAL,
                overtime_hours REAL,
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
        # Migrate any existing JSON data to SQLite
        from .migration import migrate_json_to_db
        migrate_json_to_db() 