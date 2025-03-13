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

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_pay_periods():
    """Get all pay periods from the data folder"""
    if not os.path.exists(os.path.join(DATA_FOLDER, 'pay_periods.json')):
        return []
    
    with open(os.path.join(DATA_FOLDER, 'pay_periods.json'), 'r') as f:
        return json.load(f)

def save_pay_periods(pay_periods):
    """Save pay periods to the data folder"""
    with open(os.path.join(DATA_FOLDER, 'pay_periods.json'), 'w') as f:
        json.dump(pay_periods, f)

def get_employees():
    """Get all employees from the data folder"""
    if not os.path.exists(os.path.join(DATA_FOLDER, 'employees.json')):
        return []
    
    with open(os.path.join(DATA_FOLDER, 'employees.json'), 'r') as f:
        return json.load(f)

def save_employees(employees):
    """Save employees to the data folder"""
    with open(os.path.join(DATA_FOLDER, 'employees.json'), 'w') as f:
        json.dump(employees, f)

def get_timesheet(period_id):
    """Get timesheet data for a specific pay period"""
    filename = os.path.join(DATA_FOLDER, f'timesheet_{period_id}.json')
    if not os.path.exists(filename):
        return {}
    
    with open(filename, 'r') as f:
        return json.load(f)

def save_timesheet(period_id, timesheet_data):
    """Save timesheet data for a specific pay period"""
    with open(os.path.join(DATA_FOLDER, f'timesheet_{period_id}.json'), 'w') as f:
        json.dump(timesheet_data, f)

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
        # 1. Total Pay by Employee
        plt.figure(figsize=(12, 6))
        emp_pays = [employee_total_pay[emp] for emp in active_employees]
        plt.bar(active_employees, emp_pays)
        plt.title('Total Pay by Employee')
        plt.xlabel('Employee')
        plt.ylabel('Total Pay ($)')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(os.path.join(REPORTS_FOLDER, f'total_pay_by_employee_{report_id}.png'))
        plt.close()
        
        # 2. Pay Trend Over Time
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
            
            # 3. Total Payroll by Period
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
        
        if not name:
            flash('Employee name is required', 'danger')
            return redirect(url_for('add_employee'))
        
        employees = get_employees()
        
        # Check if employee already exists
        if any(emp['name'] == name for emp in employees):
            flash('Employee already exists', 'danger')
            return redirect(url_for('add_employee'))
        
        # Add new employee
        employees.append({
            'id': str(uuid.uuid4()),
            'name': name,
            'rate': rate
        })
        
        save_employees(employees)
        flash('Employee added successfully', 'success')
        return redirect(url_for('employees'))
    
    return render_template('add_employee.html')

@app.route('/employees/edit/<employee_id>', methods=['GET', 'POST'])
def edit_employee(employee_id):
    employees = get_employees()
    employee = next((emp for emp in employees if emp['id'] == employee_id), None)
    
    if not employee:
        flash('Employee not found', 'danger')
        return redirect(url_for('employees'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        rate = request.form.get('rate')
        
        if not name:
            flash('Employee name is required', 'danger')
            return redirect(url_for('edit_employee', employee_id=employee_id))
        
        # Update employee
        employee['name'] = name
        employee['rate'] = rate
        
        save_employees(employees)
        flash('Employee updated successfully', 'success')
        return redirect(url_for('employees'))
    
    return render_template('edit_employee.html', employee=employee)

@app.route('/employees/delete/<employee_id>', methods=['POST'])
def delete_employee(employee_id):
    employees = get_employees()
    employees = [emp for emp in employees if emp['id'] != employee_id]
    save_employees(employees)
    
    flash('Employee deleted successfully', 'success')
    return redirect(url_for('employees'))

@app.route('/pay-periods')
def pay_periods():
    pay_periods_list = get_pay_periods()
    return render_template('pay_periods.html', pay_periods=pay_periods_list)

@app.route('/pay-periods/add', methods=['GET', 'POST'])
def add_pay_period():
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash('Start and end dates are required', 'danger')
            return redirect(url_for('add_pay_period'))
        
        # Convert to datetime objects
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Format for display
        period_name = f"{start_date.strftime('%m.%d.%y')} to {end_date.strftime('%m.%d.%y')}"
        
        pay_periods = get_pay_periods()
        
        # Check if period already exists
        if any(p['name'] == period_name for p in pay_periods):
            flash('Pay period already exists', 'danger')
            return redirect(url_for('add_pay_period'))
        
        # Add new pay period
        period_id = str(uuid.uuid4())
        pay_periods.append({
            'id': period_id,
            'name': period_name,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        })
        
        save_pay_periods(pay_periods)
        
        # Initialize timesheet for this period
        employees = get_employees()
        timesheet = {}
        
        # Generate days between start and end date
        days = []
        current_date = start_date
        while current_date <= end_date:
            days.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        
        # Initialize timesheet for each employee
        for employee in employees:
            timesheet[employee['name']] = {}
            for day in days:
                day_name = datetime.strptime(day, '%Y-%m-%d').strftime('%A').upper()
                timesheet[employee['name']][day] = {
                    'day': day_name,
                    'hours': '',
                    'pay': ''
                }
        
        save_timesheet(period_id, timesheet)
        
        flash('Pay period added successfully', 'success')
        return redirect(url_for('pay_periods'))
    
    return render_template('add_pay_period.html')

@app.route('/pay-periods/delete/<period_id>', methods=['POST'])
def delete_pay_period(period_id):
    pay_periods = get_pay_periods()
    pay_periods = [p for p in pay_periods if p['id'] != period_id]
    save_pay_periods(pay_periods)
    
    # Delete associated timesheet
    timesheet_file = os.path.join(DATA_FOLDER, f'timesheet_{period_id}.json')
    if os.path.exists(timesheet_file):
        os.remove(timesheet_file)
    
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
    
    return render_template('timesheet.html', 
                          period=period, 
                          employees=employees, 
                          timesheet=timesheet_data, 
                          days=days)

@app.route('/timesheet/<period_id>/update', methods=['POST'])
def update_timesheet(period_id):
    data = request.json
    timesheet_data = get_timesheet(period_id)
    
    employee = data.get('employee')
    day = data.get('day')
    field = data.get('field')
    value = data.get('value')
    
    if not all([employee, day, field]):
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    # Initialize if not exists
    if employee not in timesheet_data:
        timesheet_data[employee] = {}
    
    if day not in timesheet_data[employee]:
        day_name = datetime.strptime(day, '%Y-%m-%d').strftime('%A').upper()
        timesheet_data[employee][day] = {
            'day': day_name,
            'hours': '',
            'pay': ''
        }
    
    # Update field
    timesheet_data[employee][day][field] = value
    
    # If updating hours, calculate pay based on rate
    if field == 'hours' and value:
        employees = get_employees()
        employee_data = next((emp for emp in employees if emp['name'] == employee), None)
        
        if employee_data and employee_data.get('rate'):
            try:
                hours = float(value)
                rate = float(employee_data['rate'])
                pay = hours * rate
                timesheet_data[employee][day]['pay'] = str(pay)
            except (ValueError, TypeError):
                pass
    
    save_timesheet(period_id, timesheet_data)
    
    return jsonify({'success': True})

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
                    
                    save_pay_periods(pay_periods)
                    
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
                                'rate': ''
                            })
                    
                    save_employees(employees)
                    
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
                    
                    save_timesheet(period_id, timesheet)
                
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
    
    # Create a DataFrame for export
    data = []
    
    for employee, days in timesheet_data.items():
        # Add employee name
        row = [employee]
        data.append(row)
        
        # Add header row
        header = ['DAY', '', 'DATE', '', '', '', '', '', '', '', '', '', '', 'PAY']
        data.append(header)
        
        # Add days
        for day, day_data in sorted(days.items()):
            day_row = [day_data['day'], '', day, '', '', '', '', '', '', '', '', '', '', day_data['pay']]
            data.append(day_row)
        
        # Add empty row
        data.append([''] * 14)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save to Excel
    output_file = os.path.join(app.config['UPLOAD_FOLDER'], f'export_{period["name"]}.xlsx')
    df.to_excel(output_file, index=False, header=False)
    
    return send_file(output_file, as_attachment=True)

# Initialize with sample data if empty
if not os.path.exists(os.path.join(DATA_FOLDER, 'employees.json')):
    sample_employees = [
        {
            'id': str(uuid.uuid4()),
            'name': 'VICTOR LAZO',
            'rate': '20'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'SAMUEL CASTILLO',
            'rate': '18'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'JOSE MEDINA',
            'rate': '22'
        }
    ]
    save_employees(sample_employees)

if __name__ == '__main__':
    app.run(debug=True, port=5001) 