#!/usr/bin/env python
"""
Migration script to transfer data from SQLite to PostgreSQL.
This script will:
1. Extract all data from the SQLite database
2. Create the necessary tables in PostgreSQL
3. Insert the data into PostgreSQL
"""

import os
import sqlite3
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import json
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
load_dotenv()

# PostgreSQL connection parameters
PG_HOST = os.environ.get('PG_HOST', 'localhost')
PG_PORT = os.environ.get('PG_PORT', '5432')
PG_USER = os.environ.get('PG_USER', 'postgres')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'postgres')
PG_DB = os.environ.get('PG_DB', 'ccpayroll')

# SQLite database path
SQLITE_DB_PATH = 'data/payroll.db'

def connect_sqlite():
    """Connect to SQLite database and return connection"""
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"SQLite database not found at {SQLITE_DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_pg_db():
    """Create PostgreSQL database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server (without specifying database)
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database="postgres"  # Connect to the default postgres database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (PG_DB,))
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Creating PostgreSQL database: {PG_DB}")
            cursor.execute(f"CREATE DATABASE {PG_DB}")
        
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error creating PostgreSQL database: {str(e)}")
        return False

def connect_pg():
    """Connect to PostgreSQL database and return connection"""
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DB
        )
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {str(e)}")
        sys.exit(1)

def create_pg_tables(pg_conn):
    """Create tables in PostgreSQL"""
    cursor = pg_conn.cursor()
    
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
        regular_hours REAL DEFAULT 0,
        overtime_hours REAL DEFAULT 0,
        job_name TEXT,
        notes TEXT,
        FOREIGN KEY (period_id) REFERENCES pay_periods(id),
        UNIQUE (period_id, employee_name, day)
    )
    ''')
    
    pg_conn.commit()
    print("PostgreSQL tables created successfully")

def migrate_pay_periods(sqlite_conn, pg_conn):
    """Migrate pay periods from SQLite to PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Get all pay periods from SQLite
    sqlite_cursor.execute("SELECT id, name, start_date, end_date FROM pay_periods")
    pay_periods = sqlite_cursor.fetchall()
    
    if not pay_periods:
        print("No pay periods found in SQLite database")
        return
    
    # Insert pay periods into PostgreSQL
    for period in pay_periods:
        pg_cursor.execute(
            "INSERT INTO pay_periods (id, name, start_date, end_date) VALUES (%s, %s, %s, %s)",
            (period['id'], period['name'], period['start_date'], period['end_date'])
        )
    
    pg_conn.commit()
    print(f"Migrated {len(pay_periods)} pay periods")

def migrate_employees(sqlite_conn, pg_conn):
    """Migrate employees from SQLite to PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Get all employees from SQLite
    sqlite_cursor.execute("SELECT id, name, rate, install_crew, position, pay_type, salary, commission_rate FROM employees")
    employees = sqlite_cursor.fetchall()
    
    if not employees:
        print("No employees found in SQLite database")
        return
    
    # Insert employees into PostgreSQL
    for employee in employees:
        # Convert empty strings to None for numeric fields
        rate = None
        if employee['rate'] and employee['rate'] != '':
            try:
                rate = float(employee['rate'])
            except (ValueError, TypeError):
                rate = None
                
        salary = None
        if employee['salary'] and employee['salary'] != '':
            try:
                salary = float(employee['salary'])
            except (ValueError, TypeError):
                salary = None
                
        commission_rate = None
        if employee['commission_rate'] and employee['commission_rate'] != '':
            try:
                commission_rate = float(employee['commission_rate'])
            except (ValueError, TypeError):
                commission_rate = None
        
        pg_cursor.execute(
            """INSERT INTO employees 
               (id, name, rate, install_crew, position, pay_type, salary, commission_rate) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (employee['id'], employee['name'], rate, employee['install_crew'], 
             employee['position'], employee['pay_type'], salary, commission_rate)
        )
    
    pg_conn.commit()
    print(f"Migrated {len(employees)} employees")

def migrate_timesheet_entries(sqlite_conn, pg_conn):
    """Migrate timesheet entries from SQLite to PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Get all timesheet entries from SQLite
    sqlite_cursor.execute("""
        SELECT period_id, employee_name, day, hours, pay, project_name, 
               install_days, install, regular_hours, overtime_hours, job_name, notes, reimbursement 
        FROM timesheet_entries
    """)
    entries = sqlite_cursor.fetchall()
    
    if not entries:
        print("No timesheet entries found in SQLite database")
        return
    
    # Insert timesheet entries into PostgreSQL
    for entry in entries:
        pg_cursor.execute(
            """INSERT INTO timesheet_entries 
               (period_id, employee_name, day, hours, pay, project_name, 
                install_days, install, regular_hours, overtime_hours, job_name, notes, reimbursement) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (entry['period_id'], entry['employee_name'], entry['day'], entry['hours'], 
             entry['pay'], entry['project_name'], entry['install_days'], entry['install'], 
             entry['regular_hours'], entry['overtime_hours'], entry['job_name'], entry['notes'],
             entry.get('reimbursement', ''))
        )
    
    pg_conn.commit()
    print(f"Migrated {len(entries)} timesheet entries")

def main():
    print("Starting migration from SQLite to PostgreSQL...")
    
    # Create PostgreSQL database if it doesn't exist
    if not create_pg_db():
        print("Failed to create PostgreSQL database")
        sys.exit(1)
    
    # Connect to SQLite
    sqlite_conn = connect_sqlite()
    
    # Connect to PostgreSQL
    pg_conn = connect_pg()
    
    try:
        # Create tables in PostgreSQL
        create_pg_tables(pg_conn)
        
        # Migrate data
        migrate_pay_periods(sqlite_conn, pg_conn)
        migrate_employees(sqlite_conn, pg_conn)
        migrate_timesheet_entries(sqlite_conn, pg_conn)
        
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    main() 