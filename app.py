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
import logging
import random
from dotenv import load_dotenv

from ccpayroll.database import get_db, init_db
from ccpayroll.database.migration import save_timesheet_entry, save_pay_period, migrate_database

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'creative_closets_payroll_app'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
DATA_FOLDER = 'data'
REPORTS_FOLDER = 'static/reports'

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

# Set app config values
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATA_FOLDER'] = DATA_FOLDER
app.config['REPORTS_FOLDER'] = REPORTS_FOLDER

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

# Clean up SQLite database file if it exists and migration is complete
def cleanup_sqlite():
    sqlite_file = os.path.join(DATA_FOLDER, 'payroll.db')
    if os.path.exists(sqlite_file):
        # Check if we have data in PostgreSQL before deleting SQLite file
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM pay_periods')
            pay_periods_count = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) FROM employees')
            employees_count = cursor.fetchone()['count']
            
            # If we have data in PostgreSQL, we can delete the SQLite file
            if pay_periods_count > 0 or employees_count > 0:
                try:
                    os.remove(sqlite_file)
                    logger.info(f"Removed SQLite database file: {sqlite_file}")
                except Exception as e:
                    logger.error(f"Error removing SQLite database file: {str(e)}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_pay_periods():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pay_periods ORDER BY start_date DESC')
        return cursor.fetchall()

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

def get_employees():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM employees ORDER BY name')
        return cursor.fetchall()

def get_timesheet(period_id):
    """Get timesheet data for a pay period"""
    timesheet = {}
    
    # Get employees
    employees = get_employees()
    
    # Get timesheet entries
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM timesheet_entries WHERE period_id = %s',
            (period_id,)
        )
        entries = cursor.fetchall()
    
    # Get pay period details
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pay_periods WHERE id = %s', (period_id,))
        period = cursor.fetchone()
    
    if not period:
        return timesheet
    
    # Calculate date range
    start_date = datetime.strptime(period['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(period['end_date'], '%Y-%m-%d')
    days = []
    current_date = start_date
    while current_date <= end_date:
        days.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    
    # Initialize timesheet structure
    for employee in employees:
        timesheet[employee['name']] = {}
        for day in days:
            timesheet[employee['name']][day] = {
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
    
    # Fill in timesheet entries
    for entry in entries:
        employee_name = entry['employee_name']
        day = entry['day']
        
        if employee_name in timesheet and day in timesheet[employee_name]:
            # Fill in all fields from the entry
            for field in ['hours', 'pay', 'project_name', 'install_days', 'install', 
                         'regular_hours', 'overtime_hours', 'job_name', 'notes']:
                if entry[field] is not None:
                    timesheet[employee_name][day][field] = entry[field]
    
    return timesheet

def save_pay_period(period_data):
    """Save a pay period to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO pay_periods (id, name, start_date, end_date) VALUES (%s, %s, %s, %s) '
            'ON CONFLICT (id) DO UPDATE SET '
            'name = %s, start_date = %s, end_date = %s',
            (
                period_data['id'], period_data['name'], period_data['start_date'], period_data['end_date'],
                period_data['name'], period_data['start_date'], period_data['end_date']
            )
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
        pay_type = request.form.get('pay_type', 'hourly')
        rate = request.form.get('rate') if pay_type == 'hourly' else None
        salary = request.form.get('salary') if pay_type == 'salary' else None
        commission_rate = request.form.get('commission_rate') if pay_type == 'commission' else None
        install_crew = request.form.get('install_crew', '0')
        position = request.form.get('position', 'none')
        
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
            cursor.execute('SELECT id FROM employees WHERE name = %s', (name,))
            if cursor.fetchone():
                flash('Employee already exists', 'danger')
                return redirect(url_for('add_employee'))
        
        # Add new employee
        employee_data = {
            'id': str(uuid.uuid4()),
            'name': name,
            'pay_type': pay_type,
            'rate': rate,
            'salary': salary,
            'commission_rate': commission_rate,
            'install_crew': install_crew,
            'position': position
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
        cursor.execute('SELECT * FROM employees WHERE id = %s', (employee_id,))
        row = cursor.fetchone()
        employee = dict(row) if row else None
    
    if not employee:
        flash('Employee not found', 'danger')
        return redirect(url_for('employees'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        pay_type = request.form.get('pay_type', 'hourly')
        rate = request.form.get('rate') if pay_type == 'hourly' else None
        salary = request.form.get('salary') if pay_type == 'salary' else None
        commission_rate = request.form.get('commission_rate') if pay_type == 'commission' else None
        install_crew = request.form.get('install_crew', '0')
        position = request.form.get('position', 'none')
        
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
            'pay_type': pay_type,
            'rate': rate,
            'salary': salary,
            'commission_rate': commission_rate,
            'install_crew': install_crew,
            'position': position
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
        cursor.execute('DELETE FROM employees WHERE id = %s', (employee_id,))
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
        name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not all([start_date, end_date]):
            flash('Start date and end date are required', 'danger')
            return redirect(url_for('add_pay_period'))
        
        # If name is not provided, generate one from date range
        if not name:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                name = f"{start.strftime('%m/%d/%y')} to {end.strftime('%m/%d/%y')}"
            except Exception as e:
                app.logger.error(f"Error generating pay period name: {str(e)}")
                name = f"Pay Period {datetime.now().strftime('%m/%d/%y')}"
        
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
        cursor.execute('DELETE FROM pay_periods WHERE id = %s', (period_id,))
        # Delete associated timesheet entries
        cursor.execute('DELETE FROM timesheet_entries WHERE period_id = %s', (period_id,))
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
    
    # Organize employees by position and crew
    position_groups = {
        'install_crews': {},  # Installers (grouped by crew)
        'project_managers': [],
        'engineers': [],
        'salesmen': [],
        'ceo': [],
        'other': []
    }
    
    # First, organize installers by crew
    for employee in employees:
        position = employee.get('position', 'none')
        crew_num = employee.get('install_crew', 0)
        
        if position in ['lead', 'assistant'] and crew_num > 0:
            if crew_num not in position_groups['install_crews']:
                position_groups['install_crews'][crew_num] = []
            position_groups['install_crews'][crew_num].append(employee)
        elif position == 'project_manager':
            position_groups['project_managers'].append(employee)
        elif position == 'engineer':
            position_groups['engineers'].append(employee)
        elif position == 'salesman':
            position_groups['salesmen'].append(employee)
        elif position == 'ceo':
            position_groups['ceo'].append(employee)
        else:
            position_groups['other'].append(employee)
    
    # Sort installers within each crew - lead installers first, then assistant installers
    for crew_num in position_groups['install_crews']:
        position_groups['install_crews'][crew_num] = sorted(position_groups['install_crews'][crew_num], 
            key=lambda emp: (
                0 if emp.get('position') == 'lead' else 
                1 if emp.get('position') == 'assistant' else 2,
                emp.get('name', '')  # Secondary sort by name
            )
        )
    
    # Sort crews by number
    sorted_install_crews = sorted(position_groups['install_crews'].items())
    
    # Sort other groups by name
    for key in ['project_managers', 'engineers', 'salesmen', 'ceo', 'other']:
        position_groups[key] = sorted(position_groups[key], key=lambda emp: emp.get('name', ''))
    
    return render_template('timesheet.html', 
                          period=period, 
                          employees=employees,
                          position_groups=position_groups,
                          install_crews=sorted_install_crews,
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

@app.route('/get_employee_rate')
def get_employee_rate():
    name = request.args.get('name')
    if not name:
        return jsonify({'success': False, 'error': 'Employee name is required'})
    
    employees = get_employees()
    employee = next((e for e in employees if e['name'] == name), None)
    
    if not employee:
        return jsonify({'success': False, 'error': 'Employee not found'})
    
    rate = employee.get('rate', 0)
    return jsonify({'success': True, 'rate': rate})

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
                                'position': 'none'
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
    
    # Get pay periods to display in the dropdown
    pay_periods = get_pay_periods()
    return render_template('import.html', pay_periods=pay_periods)

@app.route('/export/<period_id>')
def export_data(period_id):
    pay_periods = get_pay_periods()
    period = next((p for p in pay_periods if p['id'] == period_id), None)
    
    if not period:
        flash('Pay period not found', 'danger')
        return redirect(url_for('pay_periods'))
    
    timesheet_data = get_timesheet(period_id)
    employees = get_employees()
    
    # Organize employees by position and crew similar to the timesheet route
    position_groups = {
        'install_crews': {},  # Installers (grouped by crew)
        'project_managers': [],
        'engineers': [],
        'salesmen': [],
        'ceo': [],
        'other': []
    }
    
    # First, organize installers by crew
    for employee in employees:
        position = employee.get('position', 'none')
        crew_num = employee.get('install_crew', 0)
        
        if position in ['lead', 'assistant'] and crew_num > 0:
            if crew_num not in position_groups['install_crews']:
                position_groups['install_crews'][crew_num] = []
            position_groups['install_crews'][crew_num].append(employee)
        elif position == 'project_manager':
            position_groups['project_managers'].append(employee)
        elif position == 'engineer':
            position_groups['engineers'].append(employee)
        elif position == 'salesman':
            position_groups['salesmen'].append(employee)
        elif position == 'ceo':
            position_groups['ceo'].append(employee)
        else:
            position_groups['other'].append(employee)
    
    # Sort installers within each crew - lead installers first, then assistant installers
    for crew_num in position_groups['install_crews']:
        position_groups['install_crews'][crew_num] = sorted(position_groups['install_crews'][crew_num], 
            key=lambda emp: (
                0 if emp.get('position') == 'lead' else 
                1 if emp.get('position') == 'assistant' else 2,
                emp.get('name', '')  # Secondary sort by name
            )
        )
    
    # Sort crews by number
    sorted_install_crews = sorted(position_groups['install_crews'].items())
    
    # Sort other groups by name
    for key in ['project_managers', 'engineers', 'salesmen', 'ceo', 'other']:
        position_groups[key] = sorted(position_groups[key], key=lambda emp: emp.get('name', ''))
    
    # Create a DataFrame for export
    data = []
    
    # Add title
    data.append(['CREATIVE CLOSETS PAYROLL TIME SHEET'])
    data.append([f'PAY PERIOD: {period["name"]}'])
    data.append([])  # Empty row
    
    # Process each install crew
    for crew_num, crew_employees in sorted_install_crews:
        data.append([f'INSTALL CREW # {crew_num}'])
        
        for employee in crew_employees:
            # Add employee name
            data.append([employee['name']])
            
            # Add header row
            header = ['DAY', 'DATE', 'PROJECT NAME', 'DAYS', 'INSTALL', 'HOURS', 'PAY']
            data.append(header)
            
            # Add days
            total_pay = 0
            total_hours = 0
            for day in sorted(timesheet_data.get(employee['name'], {}).keys()):
                day_data = timesheet_data[employee['name']][day]
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
                
                # Calculate totals
                if day_data.get('hours'):
                    try:
                        total_hours += float(day_data['hours'])
                    except (ValueError, TypeError):
                        pass
                
                if day_data.get('pay'):
                    try:
                        total_pay += float(day_data['pay'])
                    except (ValueError, TypeError):
                        pass
            
            # Add total row
            data.append(['', '', '', '', '', f'{total_hours:.1f}', f'${total_pay:.2f}'])
            
            # Add empty row
            data.append([])
    
    # Process non-install crew employees by position group
    position_titles = {
        'project_managers': 'PROJECT MANAGERS',
        'engineers': 'ENGINEERS',
        'salesmen': 'SALES TEAM',
        'ceo': 'EXECUTIVE',
        'other': 'OTHER EMPLOYEES'
    }
    
    for group_key, title in position_titles.items():
        if position_groups[group_key]:
            data.append([title])
            
            for employee in position_groups[group_key]:
                # Add employee name
                employee_display_name = employee['name']
                if employee.get('pay_type') == 'salary' and employee.get('salary'):
                    employee_display_name += f" (Salary: ${employee['salary']}/year)"
                data.append([employee_display_name])
                
                # Add header row
                is_salaried = employee.get('pay_type') == 'salary' and group_key in ['project_managers', 'engineers', 'ceo']
                
                if is_salaried:
                    # For salaried project managers, engineers, and executives, show a single row
                    header = ['PERIOD', 'PAY TYPE', 'PROJECT NAME', 'HOURS', 'PAY']
                    data.append(header)
                    
                    # Calculate weekly pay (annual salary / 52 weeks)
                    weekly_pay = 0
                    if employee.get('salary'):
                        try:
                            weekly_pay = float(employee['salary']) / 52
                        except (ValueError, TypeError):
                            pass
                    
                    # Add a single row for the pay period
                    first_day = sorted(timesheet_data.get(employee['name'], {}).keys())[0] if employee['name'] in timesheet_data and timesheet_data[employee['name']] else None
                    project_name = ""
                    pay_value = str(round(weekly_pay, 2))
                    
                    if first_day and employee['name'] in timesheet_data and first_day in timesheet_data[employee['name']]:
                        day_data = timesheet_data[employee['name']][first_day]
                        project_name = day_data.get('project_name', '')
                        # If pay was manually set, use that instead of calculated weekly pay
                        if day_data.get('pay'):
                            pay_value = day_data['pay']
                    
                    data.append([
                        period['name'],
                        'Salary',
                        project_name,
                        'Salaried',
                        pay_value
                    ])
                    
                    # Add total row
                    data.append(['', '', '', '', pay_value])
                else:
                    # Standard hourly employees
                    header = ['DAY', 'DATE', 'PROJECT NAME', 'HOURS', 'PAY']
                    data.append(header)
                    
                    # Add days
                    total_pay = 0
                    total_hours = 0
                    for day in sorted(timesheet_data.get(employee['name'], {}).keys()):
                        day_data = timesheet_data[employee['name']][day]
                        day_row = [
                            day_data.get('day', ''),
                            day,
                            day_data.get('project_name', ''),
                            day_data.get('hours', ''),
                            day_data.get('pay', '')
                        ]
                        data.append(day_row)
                        
                        # Calculate totals
                        if day_data.get('hours'):
                            try:
                                total_hours += float(day_data['hours'])
                            except (ValueError, TypeError):
                                pass
                        
                        if day_data.get('pay'):
                            try:
                                total_pay += float(day_data['pay'])
                            except (ValueError, TypeError):
                                pass
                    
                    # Add total row
                    data.append(['', '', '', f'{total_hours:.1f}', f'${total_pay:.2f}'])
                
                # Add empty row
                data.append([])
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save to Excel - sanitize period name for filename
    safe_period_name = period["name"].replace('/', '-').replace('\\', '-').replace(':', '-')
    output_file = os.path.join(app.config['UPLOAD_FOLDER'], f'export_{safe_period_name}.xlsx')
    df.to_excel(output_file, index=False, header=False)
    
    return send_file(output_file, as_attachment=True)

@app.route('/fix-timesheet/<period_id>', methods=['GET'])
def fix_timesheet(period_id):
    try:
        # Delete all timesheet entries for this period and recreate an empty structure
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM timesheet_entries WHERE period_id = %s', (period_id,))
            conn.commit()
        
        flash('Timesheet has been reset. Please re-enter your data.', 'warning')
    except Exception as e:
        app.logger.error(f"Error fixing timesheet: {str(e)}")
        flash('Failed to fix timesheet', 'danger')
    
    return redirect(url_for('timesheet', period_id=period_id))

# Initialize with sample data if empty
if not os.path.exists(os.path.join(DATA_FOLDER, 'employees.json')):
    sample_employees = [
        # Hourly employees - installers
        {
            'id': str(uuid.uuid4()),
            'name': 'VICTOR LAZO',
            'pay_type': 'hourly',
            'rate': '20',
            'salary': None,
            'commission_rate': None,
            'install_crew': 1,
            'position': 'lead'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'SAMUEL CASTILLO',
            'pay_type': 'hourly',
            'rate': '18',
            'salary': None,
            'commission_rate': None,
            'install_crew': 1,
            'position': 'assistant'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'JOSE MEDINA',
            'pay_type': 'hourly',
            'rate': '22',
            'salary': None,
            'commission_rate': None,
            'install_crew': 0,
            'position': 'none'
        },
        # Salary employees
        {
            'id': str(uuid.uuid4()),
            'name': 'ROBERT SMITH',
            'pay_type': 'salary',
            'rate': None,
            'salary': '85000',
            'commission_rate': None,
            'install_crew': 0,
            'position': 'project_manager'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'LISA JOHNSON',
            'pay_type': 'salary',
            'rate': None,
            'salary': '150000',
            'commission_rate': None,
            'install_crew': 0,
            'position': 'ceo'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'MICHAEL CHEN',
            'pay_type': 'salary',
            'rate': None,
            'salary': '95000',
            'commission_rate': None,
            'install_crew': 0,
            'position': 'engineer'
        },
        # Commission employees
        {
            'id': str(uuid.uuid4()),
            'name': 'SARAH DAVIS',
            'pay_type': 'commission',
            'rate': None,
            'salary': None,
            'commission_rate': '12',
            'install_crew': 0,
            'position': 'salesman'
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

if __name__ == '__main__':
    # Initialize database within application context
    app.app_context().push()
    init_db()
    migrate_database()
    cleanup_sqlite()
    
    app.run(debug=True) 