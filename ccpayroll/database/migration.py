"""
Database migration utilities
"""

import os
import json
import uuid
from flask import current_app
from . import get_db

def migrate_json_to_db():
    """Migrate data from JSON files to the PostgreSQL database
    
    This is only used for backward compatibility with the old JSON-based storage.
    """
    # Check if we need to migrate (if tables are empty)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM pay_periods')
        pay_periods_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) FROM employees')
        employees_count = cursor.fetchone()['count']
        
        # If we already have data, skip migration
        if pay_periods_count > 0 or employees_count > 0:
            return
    
    data_folder = current_app.config['DATA_FOLDER']
    
    # Migrate pay periods
    try_migrate_pay_periods(data_folder)
    
    # Migrate employees
    try_migrate_employees(data_folder)
    
    # Migrate timesheets
    try_migrate_timesheets(data_folder)

def try_migrate_pay_periods(data_folder):
    """Attempt to migrate pay periods from JSON file"""
    json_path = os.path.join(data_folder, 'pay_periods.json')
    if not os.path.exists(json_path):
        return
    
    try:
        with open(json_path, 'r') as f:
            pay_periods = json.load(f)
        
        for period in pay_periods:
            save_pay_period(period)
        current_app.logger.info("Migrated pay periods from JSON to database")
    except Exception as e:
        current_app.logger.error(f"Error migrating pay periods: {str(e)}")

def try_migrate_employees(data_folder):
    """Attempt to migrate employees from JSON file"""
    json_path = os.path.join(data_folder, 'employees.json')
    if not os.path.exists(json_path):
        return
    
    try:
        with open(json_path, 'r') as f:
            employees = json.load(f)
        
        for employee in employees:
            save_employee(employee)
        current_app.logger.info("Migrated employees from JSON to database")
    except Exception as e:
        current_app.logger.error(f"Error migrating employees: {str(e)}")

def try_migrate_timesheets(data_folder):
    """Attempt to migrate timesheet data from JSON files"""
    for filename in os.listdir(data_folder):
        if not (filename.startswith('timesheet_') and filename.endswith('.json')):
            continue
        
        try:
            period_id = filename.replace('timesheet_', '').replace('.json', '')
            with open(os.path.join(data_folder, filename), 'r') as f:
                timesheet_data = json.load(f)
            
            for employee_name, days in timesheet_data.items():
                for day, data in days.items():
                    for field, value in data.items():
                        if value:  # Only save non-empty values
                            save_timesheet_entry(period_id, employee_name, day, field, value)
            
            current_app.logger.info(f"Migrated timesheet {filename} to database")
        except Exception as e:
            current_app.logger.error(f"Error migrating timesheet {filename}: {str(e)}")

def save_pay_period(period_data):
    """Save a pay period to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO pay_periods (id, name, start_date, end_date) VALUES (%s, %s, %s, %s) '
            'ON CONFLICT (id) DO UPDATE SET name = %s, start_date = %s, end_date = %s',
            (
                period_data['id'], period_data['name'], period_data['start_date'], period_data['end_date'],
                period_data['name'], period_data['start_date'], period_data['end_date']
            )
        )
        conn.commit()

def save_employee(employee_data):
    """Save an employee to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Generate ID if it doesn't exist
        if 'id' not in employee_data or not employee_data['id']:
            employee_data['id'] = str(uuid.uuid4())
        
        # Set default values if they don't exist
        employee_data.setdefault('rate', None)
        employee_data.setdefault('install_crew', 0)
        employee_data.setdefault('position', None)
        employee_data.setdefault('pay_type', 'hourly')
        employee_data.setdefault('salary', None)
        employee_data.setdefault('commission_rate', None)
        
        cursor.execute(
            'INSERT INTO employees (id, name, rate, install_crew, position, pay_type, salary, commission_rate) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s) '
            'ON CONFLICT (id) DO UPDATE SET '
            'name = %s, rate = %s, install_crew = %s, position = %s, pay_type = %s, salary = %s, commission_rate = %s',
            (
                employee_data['id'], employee_data['name'], employee_data['rate'], 
                employee_data['install_crew'], employee_data['position'], 
                employee_data['pay_type'], employee_data['salary'], employee_data['commission_rate'],
                employee_data['name'], employee_data['rate'], 
                employee_data['install_crew'], employee_data['position'], 
                employee_data['pay_type'], employee_data['salary'], employee_data['commission_rate']
            )
        )
        conn.commit()

def save_timesheet_entry(period_id, employee_name, day, field, value):
    """Save a timesheet entry to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if the entry exists
        cursor.execute(
            'SELECT id FROM timesheet_entries WHERE period_id = %s AND employee_name = %s AND day = %s',
            (period_id, employee_name, day)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update the existing entry with the new field value
            sql = f'UPDATE timesheet_entries SET {field} = %s WHERE id = %s'
            cursor.execute(sql, (value, existing['id']))
        else:
            # Create a new entry with this field set
            # Set all fields except the one being updated to NULL
            fields = ['period_id', 'employee_name', 'day', field]
            values = [period_id, employee_name, day, value]
            
            placeholders = ', '.join(['%s'] * len(fields))
            fields_str = ', '.join(fields)
            
            sql = f'INSERT INTO timesheet_entries ({fields_str}) VALUES ({placeholders})'
            cursor.execute(sql, values)
        
        conn.commit()

def migrate_database():
    """Run any necessary database migrations"""
    # This function is a placeholder for future migrations
    current_app.logger.info("No migrations needed") 