import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def get_db_url():
    """Get the database URL from environment variables"""
    return os.environ.get('DATABASE_URL')

def init_db():
    """Initialize the database with required tables"""
    db_url = get_db_url()
    
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Handle old-style heroku postgres URLs if necessary
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    print(f"Connecting to database at {db_url[:db_url.index('@')]}")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
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
        print("Created pay_periods table")
        
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
        print("Created employees table")
        
        # Create timesheet_entries table
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
        print("Created timesheet_entries table")
        
        cursor.close()
        conn.close()
        print("Database initialization complete")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    init_db() 