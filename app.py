from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
import json
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import uuid
import sqlite3
from contextlib import contextmanager
import threading
import logging
import random

app = Flask(__name__)
app.secret_key = 'creative_closets_payroll_app'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
DATA_FOLDER = 'data'
REPORTS_FOLDER = 'static/reports'
DATABASE_PATH = os.path.join(DATA_FOLDER, 'payroll.db')

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(DATA_FOLDER, 'payroll.log'))
    ]
)
logger = logging.getLogger('payroll')

# Thread-local storage for database connections
db_local = threading.local()
db_connections = {}  # Track connections for monitoring

# Database setup
def init_db():
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
            installer_role TEXT
        )
        ''')
        
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

@contextmanager
def get_db():
    """Context manager for getting database connection"""
    thread_id = threading.get_ident()
    
    if not hasattr(db_local, 'connection'):
        db_local.connection = sqlite3.connect(DATABASE_PATH)
        db_local.connection.row_factory = sqlite3.Row
        db_connections[thread_id] = {
            'created_at': datetime.now(),
            'last_used': datetime.now()
        }
        logger.info(f"New DB connection created for thread {thread_id}")
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

@app.before_request
def before_request():
    """Run before each request"""
    # Periodically monitor database connections
    if random.random() < 0.01:  # 1% chance to run on each request
        monitor_db_connections()

@app.teardown_appcontext
def teardown_db(exception):
    """Close database connection at the end of the request"""
    close_db()

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_pay_periods():
    """Get all pay periods from the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pay_periods ORDER BY start_date DESC')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def save_pay_period(period_data):
    """Save a pay period to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO pay_periods (id, name, start_date, end_date) VALUES (?, ?, ?, ?)',
            (period_data['id'], period_data['name'], period_data['start_date'], period_data['end_date'])
        )
        conn.commit()

def get_employees():
    """Get all employees from the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM employees')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def save_employee(employee_data):
    """Save an employee to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO employees (id, name, rate, install_crew, installer_role) VALUES (?, ?, ?, ?, ?)',
            (employee_data['id'], employee_data['name'], employee_data['rate'], 
             employee_data['install_crew'], employee_data['installer_role'])
        )
        conn.commit()

def get_timesheet(period_id):
    """Get timesheet data for a specific pay period"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT employee_name, day, hours, pay, project_name, install_days, install FROM timesheet_entries WHERE period_id = ?',
            (period_id,)
        )
        rows = cursor.fetchall()
        
        # Restructure data to match the original format
        timesheet_data = {}
        for row in rows:
            employee_name = row['employee_name']
            day = row['day']
            
            if employee_name not in timesheet_data:
                timesheet_data[employee_name] = {}
                
            timesheet_data[employee_name][day] = {
                'hours': row['hours'] or '',
                'pay': row['pay'] or '',
                'project_name': row['project_name'] or '',
                'install_days': row['install_days'] or '',
                'install': row['install'] or ''
            }
        
        return timesheet_data

def save_timesheet_entry(period_id, employee_name, day, field, value):
    """Save a timesheet entry for a specific field"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if entry exists
        cursor.execute(
            'SELECT * FROM timesheet_entries WHERE period_id = ? AND employee_name = ? AND day = ?',
            (period_id, employee_name, day)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update specific field
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
                'install': ''
            }
            # Set the specified field
            fields[field] = value
            
            # Insert new entry
            cursor.execute(
                '''
                INSERT INTO timesheet_entries 
                (period_id, employee_name, day, hours, pay, project_name, install_days, install)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (period_id, employee_name, day, fields['hours'], fields['pay'], 
                 fields['project_name'], fields['install_days'], fields['install'])
            )
        
        conn.commit()

def generate_report(period_id=None):
    """Generate payroll report for a specific period or all periods"""
    pay_periods = get_pay_periods()
    employees = get_employees()
    
    if period_id:
        # Filter to specific period
        periods_to_process = [p for p in pay_periods if p['id'] == period_id]
    else:
        # Process all periods
        periods_to_process = pay_periods
    
    # Initialize data structures for report
    employee_total_pay = {emp['name']: 0 for emp in employees}
    employee_pay_by_period = {emp['name']: [] for emp in employees}
    period_totals = {}
    
    # Process each pay period
    for period in periods_to_process:
        period_id = period['id']
        timesheet = get_timesheet(period_id)
        
        period_total = 0
        period_data = {'period': period['name']}
        
        # Process each employee
        for employee in employees:
            emp_name = employee['name']
            employee_total = 0
            
            # Get employee data for this period
            if emp_name in timesheet:
                for day, day_data in timesheet[emp_name].items():
                    if 'pay' in day_data and day_data['pay']:
                        try:
                            pay = float(day_data['pay'])
                            employee_total += pay
                        except (ValueError, TypeError):
                            pass
            
            # Update totals
            employee_total_pay[emp_name] += employee_total
            employee_pay_by_period[emp_name].append({
                'period': period['name'],
                'pay': employee_total
            })
            
            period_data[emp_name] = employee_total
            period_total += employee_total
        
        period_data['total'] = period_total
        period_totals[period['name']] = period_data
    
    # Generate visualizations
    report_id = str(uuid.uuid4())
    
    # Filter to employees with non-zero pay
    active_employees = [emp['name'] for emp in employees if employee_total_pay[emp['name']] > 0]
    
    if active_employees:
        # Only generate multi-period graphs if we have more than one period
        if len(periods_to_process) > 1:
            plt.figure(figsize=(12, 6))
            for employee in active_employees:
                periods = [p['period'] for p in employee_pay_by_period[employee]]
                pays = [p['pay'] for p in employee_pay_by_period[employee]]
                if any(pay > 0 for pay in pays):
                    plt.plot(range(len(periods)), pays, marker='o', label=employee)
            
            plt.title('Pay Trend Over Time')
            plt.xlabel('Pay Period')
            plt.ylabel('Pay Amount ($)')
            plt.xticks(range(len(periods_to_process)), [p['name'] for p in periods_to_process], rotation=45, ha='right')
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(os.path.join(REPORTS_FOLDER, f'pay_trend_over_time_{report_id}.png'))
            plt.close()
            
            # Total Payroll by Period
            plt.figure(figsize=(12, 6))
            period_names = [p['name'] for p in periods_to_process]
            period_sums = [sum(period_totals[p]['total'] for p in period_names if p in period_totals)]
            plt.bar(range(len(period_names)), period_sums)
            plt.title('Total Payroll by Period')
            plt.xlabel('Pay Period')
            plt.ylabel('Total Payroll ($)')
            plt.xticks(range(len(period_names)), period_names, rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig(os.path.join(REPORTS_FOLDER, f'total_payroll_by_period_{report_id}.png'))
            plt.close()
    
    return {
        'report_id': report_id,
        'employee_total_pay': employee_total_pay,
        'employee_pay_by_period': employee_pay_by_period,
        'period_totals': period_totals,
        'active_employees': active_employees,
        'periods_processed': [p['name'] for p in periods_to_process]
    }

# Routes
@app.route('/')
def index():
    pay_periods = get_pay_periods()
    return render_template('index.html', pay_periods=pay_periods)

@app.route('/employees')
def employees():
    employees_list = get_employees()
    return render_template('employees.html', employees=employees_list)

@app.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        rate = request.form.get('rate')
        install_crew = request.form.get('install_crew', '0')
        installer_role = request.form.get('installer_role', 'none')
        
        # Convert install_crew to integer
        try:
            install_crew = int(install_crew)
        except (ValueError, TypeError):
            install_crew = 0
        
        if not name:
            flash('Employee name is required', 'danger')
            return redirect(url_for('add_employee'))
        
        # Check if employee already exists
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM employees WHERE name = ?', (name,))
            if cursor.fetchone():
                flash('Employee already exists', 'danger')
                return redirect(url_for('add_employee'))
        
        # Add new employee
        employee_data = {
            'id': str(uuid.uuid4()),
            'name': name,
            'rate': rate,
            'install_crew': install_crew,
            'installer_role': installer_role
        }
        save_employee(employee_data)
        
        flash('Employee added successfully', 'success')
        return redirect(url_for('employees'))
    
    return render_template('add_employee.html')

@app.route('/employees/edit/<employee_id>', methods=['GET', 'POST'])
def edit_employee(employee_id):
    # Get the employee from the database
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM employees WHERE id = ?', (employee_id,))
        row = cursor.fetchone()
        employee = dict(row) if row else None
    
    if not employee:
        flash('Employee not found', 'danger')
        return redirect(url_for('employees'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        rate = request.form.get('rate')
        install_crew = request.form.get('install_crew', '0')
        installer_role = request.form.get('installer_role', 'none')
        
        # Convert install_crew to integer
        try:
            install_crew = int(install_crew)
        except (ValueError, TypeError):
            install_crew = 0
        
        if not name:
            flash('Employee name is required', 'danger')
            return redirect(url_for('edit_employee', employee_id=employee_id))
        
        # Update employee in database
        employee = {
            'id': employee_id,
            'name': name,
            'rate': rate,
            'install_crew': install_crew,
            'installer_role': installer_role
        }
        
        save_employee(employee)
        flash('Employee updated successfully', 'success')
        return redirect(url_for('employees'))
    
    return render_template('edit_employee.html', employee=employee)

@app.route('/employees/delete/<employee_id>', methods=['POST'])
def delete_employee(employee_id):
    # Get employees and remove the one with matching ID
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
        conn.commit()
    
    flash('Employee deleted successfully', 'success')
    return redirect(url_for('employees'))

@app.route('/pay-periods')
def pay_periods():
    pay_periods_list = get_pay_periods()
    return render_template('pay_periods.html', pay_periods=pay_periods_list)

@app.route('/pay-periods/add', methods=['GET', 'POST'])
def add_pay_period():
    if request.method == 'POST':
        name = request.form.get('name')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not all([name, start_date, end_date]):
            flash('All fields are required', 'danger')
            return redirect(url_for('add_pay_period'))
        
        # Create pay period
        period_data = {
            'id': str(uuid.uuid4()),
            'name': name,
            'start_date': start_date,
            'end_date': end_date
        }
        
        save_pay_period(period_data)
        flash('Pay period added successfully', 'success')
        return redirect(url_for('pay_periods'))
    
    return render_template('add_pay_period.html')

@app.route('/pay-periods/delete/<period_id>', methods=['POST'])
def delete_pay_period(period_id):
    # Delete pay period from database
    with get_db() as conn:
        cursor = conn.cursor()
        # Delete the pay period
        cursor.execute('DELETE FROM pay_periods WHERE id = ?', (period_id,))
        # Delete associated timesheet entries
        cursor.execute('DELETE FROM timesheet_entries WHERE period_id = ?', (period_id,))
        conn.commit()
    
    # Delete any associated files (like Excel exports)
    export_file = os.path.join(UPLOAD_FOLDER, f'timesheet_{period_id}.xlsx')
    if os.path.exists(export_file):
        os.remove(export_file)
    
    flash('Pay period deleted successfully', 'success')
    return redirect(url_for('pay_periods'))

@app.route('/timesheet/<period_id>')
def timesheet(period_id):
    pay_periods = get_pay_periods()
    period = next((p for p in pay_periods if p['id'] == period_id), None)
    
    if not period:
        flash('Pay period not found', 'danger')
        return redirect(url_for('pay_periods'))
    
    employees = get_employees()
    timesheet_data = get_timesheet(period_id)
    
    # Get days in the period
    start_date = datetime.strptime(period['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(period['end_date'], '%Y-%m-%d')
    
    days = []
    current_date = start_date
    while current_date <= end_date:
        days.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'day': current_date.strftime('%A').upper()
        })
        current_date += timedelta(days=1)
    
    # Group employees by install crew
    crews = {}
    for employee in employees:
        crew_num = employee.get('install_crew', 0)
        if crew_num not in crews:
            crews[crew_num] = []
        crews[crew_num].append(employee)
    
    # Sort crews by number
    sorted_crews = sorted(crews.items())
    
    return render_template('timesheet.html', 
                          period=period, 
                          employees=employees,
                          crews=sorted_crews,
                          timesheet=timesheet_data, 
                          days=days)

@app.route('/timesheet/<period_id>/update', methods=['POST'])
def update_timesheet(period_id):
    try:
        data = request.json
        if not data or not all(k in data for k in ('employee', 'day', 'field', 'value')):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        employee = data['employee']
        day = data['day']
        field = data['field']
        value = data['value']
        calculate_only = data.get('calculate_only', False)
        
        response_data = {'success': True}
        
        # Update the specified field
        if field == 'hours' and value:
            # Get employee to check hourly rate
            employees = get_employees()
            employee_data = next((e for e in employees if e['name'] == employee), None)
            
            if employee_data:
                # Check for both 'hourly_rate' and 'rate' fields for compatibility
                hourly_rate = None
                if 'hourly_rate' in employee_data and employee_data['hourly_rate']:
                    try:
                        hourly_rate = float(employee_data['hourly_rate'])
                    except (ValueError, TypeError):
                        pass
                elif 'rate' in employee_data and employee_data['rate']:
                    try:
                        hourly_rate = float(employee_data['rate'])
                    except (ValueError, TypeError):
                        pass
                
                if hourly_rate:
                    try:
                        hours = float(value)
                        pay = hours * hourly_rate
                        response_data['pay'] = f"{pay:.2f}"
                        
                        # Only update the pay field if not in calculate_only mode
                        if not calculate_only:
                            save_timesheet_entry(period_id, employee, day, 'pay', f"{pay:.2f}")
                    except (ValueError, TypeError) as e:
                        app.logger.error(f"Error calculating pay: {str(e)}")
            
            # Always update hours field unless in calculate_only mode
            if not calculate_only:
                save_timesheet_entry(period_id, employee, day, field, value)
        else:
            # For other fields, just update normally
            if not calculate_only:
                save_timesheet_entry(period_id, employee, day, field, value)
            
        return jsonify(response_data)
    except Exception as e:
        app.logger.error(f"Error in update_timesheet: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reports')
def reports():
    pay_periods = get_pay_periods()
    return render_template('reports.html', pay_periods=pay_periods)

@app.route('/reports/generate', methods=['POST'])
def generate_report_route():
    period_id = request.form.get('period_id')
    
    if period_id == 'all':
        period_id = None
    
    report = generate_report(period_id)
    
    return render_template('report_result.html', 
                          report=report, 
                          report_id=report['report_id'])

@app.route('/import', methods=['GET', 'POST'])
def import_data():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Process the Excel file
                xl = pd.ExcelFile(filepath)
                sheet_names = xl.sheet_names
                
                # Skip the first sheet which is a template
                sheet_names = [sheet for sheet in sheet_names if sheet != 'PAYROLL TIMESHEET']
                
                # Process each sheet (pay period)
                for sheet in sheet_names:
                    df = pd.read_excel(filepath, sheet_name=sheet)
                    
                    # Extract period name from sheet name
                    period_name = sheet.replace('payroll ', '')
                    
                    # Create pay period
                    pay_periods = get_pay_periods()
                    
                    # Check if period already exists
                    if any(p['name'] == period_name for p in pay_periods):
                        continue
                    
                    # Try to parse dates from period name
                    try:
                        dates = period_name.split(' to ')
                        start_date = datetime.strptime(dates[0].strip(), '%m.%d.%y')
                        end_date = datetime.strptime(dates[1].strip(), '%m.%d.%y')
                    except:
                        # Use current date as fallback
                        start_date = datetime.now()
                        end_date = start_date + timedelta(days=6)
                    
                    # Add new pay period
                    period_id = str(uuid.uuid4())
                    pay_periods.append({
                        'id': period_id,
                        'name': period_name,
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d')
                    })
                    
                    save_pay_period(pay_periods)
                    
                    # Extract employees and timesheet data
                    employees = get_employees()
                    employee_names = set()
                    timesheet = {}
                    
                    # Find employee names (they are typically in the first column)
                    for idx, value in enumerate(df.iloc[:, 0]):
                        if pd.notna(value) and isinstance(value, str) and value.strip().upper() == value.strip() and len(value.strip()) > 3 and value.strip() not in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY', 'DAY', 'DATE', 'CREATIVE CLOSETS PAYROLL TIME SHEET']:
                            employee_names.add(value.strip())
                    
                    # Add new employees
                    for emp_name in employee_names:
                        if not any(emp['name'] == emp_name for emp in employees):
                            employees.append({
                                'id': str(uuid.uuid4()),
                                'name': emp_name,
                                'rate': '',
                                'install_crew': 0,
                                'installer_role': 'none'
                            })
                    
                    save_employee(employees)
                    
                    # Find the PAY column
                    pay_col_idx = None
                    for col_idx, col_name in enumerate(df.iloc[1]):
                        if pd.notna(col_name) and isinstance(col_name, str) and 'PAY' in col_name.upper():
                            pay_col_idx = col_idx
                            break
                    
                    if pay_col_idx is None:
                        continue
                    
                    # Generate days between start and end date
                    days = []
                    current_date = start_date
                    while current_date <= end_date:
                        days.append(current_date.strftime('%Y-%m-%d'))
                        current_date += timedelta(days=1)
                    
                    # Initialize timesheet for each employee
                    for employee in employee_names:
                        timesheet[employee] = {}
                        
                        # Find rows for this employee
                        employee_rows = []
                        employee_found = False
                        
                        for idx, row in df.iterrows():
                            if pd.notna(row.iloc[0]) and isinstance(row.iloc[0], str) and row.iloc[0].strip() == employee:
                                employee_found = True
                            elif employee_found and pd.notna(row.iloc[0]) and isinstance(row.iloc[0], str) and row.iloc[0].strip() in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']:
                                employee_rows.append(row)
                            elif employee_found and pd.notna(row.iloc[0]) and isinstance(row.iloc[0], str) and row.iloc[0].strip().upper() == row.iloc[0].strip() and len(row.iloc[0].strip()) > 3 and row.iloc[0].strip() not in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY', 'DAY', 'DATE']:
                                # Found next employee
                                employee_found = False
                        
                        # Map days to employee rows
                        for i, day in enumerate(days):
                            if i < len(employee_rows):
                                row = employee_rows[i]
                                day_name = datetime.strptime(day, '%Y-%m-%d').strftime('%A').upper()
                                
                                # Extract pay
                                pay = ''
                                if pd.notna(row.iloc[pay_col_idx]) and row.iloc[pay_col_idx] != '':
                                    try:
                                        pay = str(float(row.iloc[pay_col_idx]))
                                    except (ValueError, TypeError):
                                        pass
                                
                                timesheet[employee][day] = {
                                    'day': day_name,
                                    'hours': '',
                                    'pay': pay
                                }
                            else:
                                day_name = datetime.strptime(day, '%Y-%m-%d').strftime('%A').upper()
                                timesheet[employee][day] = {
                                    'day': day_name,
                                    'hours': '',
                                    'pay': ''
                                }
                    
                    save_timesheet_entry(period_id, employee, day, field, value)
                
                flash('Data imported successfully', 'success')
                return redirect(url_for('index'))
            
            except Exception as e:
                flash(f'Error importing data: {str(e)}', 'danger')
                return redirect(url_for('import_data'))
    
    return render_template('import.html')

@app.route('/export/<period_id>')
def export_data(period_id):
    pay_periods = get_pay_periods()
    period = next((p for p in pay_periods if p['id'] == period_id), None)
    
    if not period:
        flash('Pay period not found', 'danger')
        return redirect(url_for('pay_periods'))
    
    timesheet_data = get_timesheet(period_id)
    employees = get_employees()
    
    # Group employees by install crew
    crews = {}
    for employee in employees:
        crew_num = employee.get('install_crew', 0)
        if crew_num not in crews:
            crews[crew_num] = []
        crews[crew_num].append(employee)
    
    # Sort crews by number
    sorted_crews = sorted(crews.items())
    
    # Create a DataFrame for export
    data = []
    
    # Add title
    data.append(['CREATIVE CLOSETS PAYROLL TIME SHEET'])
    data.append([])  # Empty row
    
    # Process each crew
    for crew_num, crew_employees in sorted_crews:
        if crew_num > 0:  # Only process install crews
            data.append([f'INSTALL CREW # {crew_num}'])
            
            for employee in crew_employees:
                # Add employee name
                data.append([employee['name']])
                
                # Add header row
                header = ['DAY', 'DATE', 'PROJECT NAME', 'DAYS', 'INSTALL', 'HOURS', 'PAY']
                data.append(header)
                
                # Add days
                total_pay = 0
                for day, day_data in sorted(timesheet_data.get(employee['name'], {}).items()):
                    day_row = [
                        day_data.get('day', ''),
                        day,
                        day_data.get('project_name', ''),
                        day_data.get('install_days', ''),
                        day_data.get('install', ''),
                        day_data.get('hours', ''),
                        day_data.get('pay', '')
                    ]
                    data.append(day_row)
                    
                    # Calculate total pay
                    if day_data.get('pay'):
                        try:
                            total_pay += float(day_data['pay'])
                        except (ValueError, TypeError):
                            pass
                
                # Add total row
                data.append(['', '', '', '', '', 'TOTAL', f'${total_pay:.2f}'])
                
                # Add empty row
                data.append([])
    
    # Process non-crew employees
    if 0 in crews:
        data.append(['OTHER EMPLOYEES'])
        
        for employee in crews[0]:
            # Add employee name
            data.append([employee['name']])
            
            # Add header row
            header = ['DAY', 'DATE', 'PROJECT NAME', 'HOURS', 'PAY']
            data.append(header)
            
            # Add days
            total_pay = 0
            for day, day_data in sorted(timesheet_data.get(employee['name'], {}).items()):
                day_row = [
                    day_data.get('day', ''),
                    day,
                    day_data.get('project_name', ''),
                    day_data.get('hours', ''),
                    day_data.get('pay', '')
                ]
                data.append(day_row)
                
                # Calculate total pay
                if day_data.get('pay'):
                    try:
                        total_pay += float(day_data['pay'])
                    except (ValueError, TypeError):
                        pass
            
            # Add total row
            data.append(['', '', '', 'TOTAL', f'${total_pay:.2f}'])
            
            # Add empty row
            data.append([])
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save to Excel
    output_file = os.path.join(app.config['UPLOAD_FOLDER'], f'export_{period["name"]}.xlsx')
    df.to_excel(output_file, index=False, header=False)
    
    return send_file(output_file, as_attachment=True)

@app.route('/fix-timesheet/<period_id>', methods=['GET'])
def fix_timesheet(period_id):
    try:
        # Delete all timesheet entries for this period and recreate an empty structure
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM timesheet_entries WHERE period_id = ?', (period_id,))
            conn.commit()
        
        flash('Timesheet has been reset. Please re-enter your data.', 'warning')
    except Exception as e:
        app.logger.error(f"Error fixing timesheet: {str(e)}")
        flash('Failed to fix timesheet', 'danger')
    
    return redirect(url_for('timesheet', period_id=period_id))

# Initialize with sample data if empty
if not os.path.exists(os.path.join(DATA_FOLDER, 'employees.json')):
    sample_employees = [
        {
            'id': str(uuid.uuid4()),
            'name': 'VICTOR LAZO',
            'rate': '20',
            'install_crew': 1,
            'installer_role': 'lead'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'SAMUEL CASTILLO',
            'rate': '18',
            'install_crew': 1,
            'installer_role': 'assistant'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'JOSE MEDINA',
            'rate': '22',
            'install_crew': 0,
            'installer_role': 'none'
        }
    ]
    # Save each employee individually
    for employee in sample_employees:
        save_employee(employee)

# Initialize database and migrate data from JSON if needed
def migrate_json_to_db():
    """Migrate data from JSON files to the SQLite database"""
    # Check if we need to migrate (if tables are empty)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM pay_periods')
        pay_periods_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM employees')
        employees_count = cursor.fetchone()[0]
        
        # If we already have data, skip migration
        if pay_periods_count > 0 or employees_count > 0:
            return
        
        # Migrate pay periods
        if os.path.exists(os.path.join(DATA_FOLDER, 'pay_periods.json')):
            try:
                with open(os.path.join(DATA_FOLDER, 'pay_periods.json'), 'r') as f:
                    pay_periods = json.load(f)
                    for period in pay_periods:
                        save_pay_period(period)
                app.logger.info("Migrated pay periods from JSON to database")
            except Exception as e:
                app.logger.error(f"Error migrating pay periods: {str(e)}")
        
        # Migrate employees
        if os.path.exists(os.path.join(DATA_FOLDER, 'employees.json')):
            try:
                with open(os.path.join(DATA_FOLDER, 'employees.json'), 'r') as f:
                    employees = json.load(f)
                    for employee in employees:
                        save_employee(employee)
                app.logger.info("Migrated employees from JSON to database")
            except Exception as e:
                app.logger.error(f"Error migrating employees: {str(e)}")
        
        # Migrate timesheets
        for filename in os.listdir(DATA_FOLDER):
            if filename.startswith('timesheet_') and filename.endswith('.json'):
                try:
                    period_id = filename.replace('timesheet_', '').replace('.json', '')
                    
                    with open(os.path.join(DATA_FOLDER, filename), 'r') as f:
                        timesheet_data = json.load(f)
                        
                        for employee_name, days in timesheet_data.items():
                            for day, data in days.items():
                                for field, value in data.items():
                                    if value:  # Only save non-empty values
                                        save_timesheet_entry(period_id, employee_name, day, field, value)
                    
                    app.logger.info(f"Migrated timesheet {filename} to database")
                except Exception as e:
                    app.logger.error(f"Error migrating timesheet {filename}: {str(e)}")

# Initialize the database
init_db()

# Migrate existing JSON data to the database
migrate_json_to_db()

if __name__ == '__main__':
    app.run(debug=True, port=5001) 