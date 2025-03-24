#!/usr/bin/env python
"""
Simple initialization script to create the database tables on Heroku
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('init_db')

def init_db():
    """Initialize the database schema directly without Flask app context"""
    logger.info("Initializing database tables directly...")
    
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        logger.error("No DATABASE_URL environment variable found")
        return
    
    # Handle Heroku's postgres:// vs postgresql:// in the connection URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        # Connect to PostgreSQL
        logger.info(f"Connecting to database...")
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
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
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    init_db() 