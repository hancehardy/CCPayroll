"""
Database migration utilities
"""

import os
import json
import logging
import uuid
from flask import current_app
from contextlib import contextmanager

from ccpayroll.database import get_db, init_db

logger = logging.getLogger('payroll.migration')

def migrate_json_to_db(data_folder='data'):
    """Migrate data from JSON files to the database"""
    # Check if we need to migrate (if tables are empty)
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT COUNT(*) FROM pay_periods')
            pay_periods_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM employees')
            employees_count = cursor.fetchone()[0]
            
            # If we already have data, skip migration
            if pay_periods_count > 0 or employees_count > 0:
                return
        except Exception as e:
            logger.error(f"Error checking tables: {str(e)}")
            return
        
        # Migrate pay periods
        if os.path.exists(os.path.join(data_folder, 'pay_periods.json')):
            try:
                with open(os.path.join(data_folder, 'pay_periods.json'), 'r') as f:
                    pay_periods = json.load(f)
                    for period in pay_periods:
                        save_pay_period(period)
                logger.info("Migrated pay periods from JSON to database")
            except Exception as e:
                logger.error(f"Error migrating pay periods: {str(e)}")
        
        # Migrate employees
        if os.path.exists(os.path.join(data_folder, 'employees.json')):
            try:
                with open(os.path.join(data_folder, 'employees.json'), 'r') as f:
                    employees = json.load(f)
                    for employee in employees:
                        save_employee(employee)
                logger.info("Migrated employees from JSON to database")
            except Exception as e:
                logger.error(f"Error migrating employees: {str(e)}")
        
        # Migrate timesheets
        for filename in os.listdir(data_folder):
            if filename.startswith('timesheet_') and filename.endswith('.json'):
                try:
                    period_id = filename.replace('timesheet_', '').replace('.json', '')
                    
                    with open(os.path.join(data_folder, filename), 'r') as f:
                        timesheet_data = json.load(f)
                        
                        for employee_name, days in timesheet_data.items():
                            for day, data in days.items():
                                for field, value in data.items():
                                    if value:  # Only save non-empty values
                                        save_timesheet_entry(period_id, employee_name, day, field, value)
                    
                    logger.info(f"Migrated timesheet {filename} to database")
                except Exception as e:
                    logger.error(f"Error migrating timesheet {filename}: {str(e)}")

def save_pay_period(period_data):
    """Save a pay period to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if PostgreSQL connection
        if hasattr(conn, '_con') and conn._con.__class__.__module__.startswith('psycopg2'):
            # PostgreSQL syntax
            cursor.execute(
                '''
                INSERT INTO pay_periods (id, name, start_date, end_date) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date
                ''',
                (period_data['id'], period_data['name'], period_data['start_date'], period_data['end_date'])
            )
        else:
            # SQLite syntax
            cursor.execute(
                'INSERT OR REPLACE INTO pay_periods (id, name, start_date, end_date) VALUES (?, ?, ?, ?)',
                (period_data['id'], period_data['name'], period_data['start_date'], period_data['end_date'])
            )
            
        conn.commit()

def save_employee(employee_data):
    """Save an employee to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if PostgreSQL connection
        if hasattr(conn, '_con') and conn._con.__class__.__module__.startswith('psycopg2'):
            # PostgreSQL syntax
            cursor.execute(
                '''
                INSERT INTO employees (
                    id, name, rate, install_crew, position, 
                    pay_type, salary, commission_rate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    rate = EXCLUDED.rate,
                    install_crew = EXCLUDED.install_crew,
                    position = EXCLUDED.position,
                    pay_type = EXCLUDED.pay_type,
                    salary = EXCLUDED.salary,
                    commission_rate = EXCLUDED.commission_rate
                ''',
                (
                    employee_data['id'], 
                    employee_data['name'], 
                    employee_data.get('rate'), 
                    employee_data.get('install_crew', 0), 
                    employee_data.get('position', 'none'),
                    employee_data.get('pay_type', 'hourly'),
                    employee_data.get('salary'),
                    employee_data.get('commission_rate')
                )
            )
        else:
            # SQLite syntax
            cursor.execute(
                '''
                INSERT OR REPLACE INTO employees (
                    id, name, rate, install_crew, position, 
                    pay_type, salary, commission_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    employee_data['id'], 
                    employee_data['name'], 
                    employee_data.get('rate'), 
                    employee_data.get('install_crew', 0), 
                    employee_data.get('position', 'none'),
                    employee_data.get('pay_type', 'hourly'),
                    employee_data.get('salary'),
                    employee_data.get('commission_rate')
                )
            )
            
        conn.commit()

def save_timesheet_entry(period_id, employee_name, day, field, value):
    """Save a timesheet entry for a specific field"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if PostgreSQL connection
        is_postgres = hasattr(conn, '_con') and conn._con.__class__.__module__.startswith('psycopg2')
        
        # Check if entry exists
        if is_postgres:
            cursor.execute(
                'SELECT * FROM timesheet_entries WHERE period_id = %s AND employee_name = %s AND day = %s',
                (period_id, employee_name, day)
            )
        else:
            cursor.execute(
                'SELECT * FROM timesheet_entries WHERE period_id = ? AND employee_name = ? AND day = ?',
                (period_id, employee_name, day)
            )
            
        existing = cursor.fetchone()
        
        if existing:
            # Update specific field
            if is_postgres:
                cursor.execute(
                    f'UPDATE timesheet_entries SET {field} = %s WHERE period_id = %s AND employee_name = %s AND day = %s',
                    (value, period_id, employee_name, day)
                )
            else:
                cursor.execute(
                    f'UPDATE timesheet_entries SET {field} = ? WHERE period_id = ? AND employee_name = ? AND day = ?',
                    (value, period_id, employee_name, day)
                )
        else:
            # Default values for all fields
            fields = {
                'hours': '',
                'pay': '',
                'project_name': '',
                'install_days': '',
                'install': '',
                'regular_hours': 0,
                'overtime_hours': 0,
                'job_name': '',
                'notes': ''
            }
            # Set the specified field
            fields[field] = value
            
            # Insert new entry
            if is_postgres:
                cursor.execute(
                    '''
                    INSERT INTO timesheet_entries 
                    (period_id, employee_name, day, hours, pay, project_name, install_days, install,
                    regular_hours, overtime_hours, job_name, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''',
                    (period_id, employee_name, day, 
                     fields['hours'], fields['pay'], 
                     fields['project_name'], fields['install_days'], fields['install'],
                     fields['regular_hours'], fields['overtime_hours'],
                     fields['job_name'], fields['notes'])
                )
            else:
                cursor.execute(
                    '''
                    INSERT INTO timesheet_entries 
                    (period_id, employee_name, day, hours, pay, project_name, install_days, install,
                    regular_hours, overtime_hours, job_name, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (period_id, employee_name, day, 
                     fields['hours'], fields['pay'], 
                     fields['project_name'], fields['install_days'], fields['install'],
                     fields['regular_hours'], fields['overtime_hours'],
                     fields['job_name'], fields['notes'])
                )
        
        conn.commit()

def migrate_database():
    """Run any necessary database migrations"""
    try:
        # First ensure the database is initialized
        init_db()
        
        # Then migrate any JSON data
        migrate_json_to_db()
        
        logger.info("Database migration completed successfully")
    except Exception as e:
        logger.error(f"Error during database migration: {str(e)}")
        raise 