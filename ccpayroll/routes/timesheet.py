"""
Timesheet routes for Creative Closets Payroll

This module handles timesheet-related routes, including viewing and editing timesheet entries.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..models import Employee, PayPeriod, TimesheetEntry
from ..utils import format_date

timesheet = Blueprint('timesheet', __name__, url_prefix='/timesheet')

@timesheet.route('/')
def index():
    """Display timesheet selection page"""
    pay_periods = PayPeriod.get_all()
    employees = Employee.get_all()
    
    return render_template(
        'timesheet/index.html',
        pay_periods=pay_periods,
        employees=employees
    )

@timesheet.route('/view/<period_id>/<employee_id>')
def view(period_id, employee_id):
    """View timesheet for a specific pay period and employee"""
    pay_period = PayPeriod.get_by_id(period_id)
    employee = Employee.get_by_id(employee_id)
    
    if not pay_period or not employee:
        flash('Pay period or employee not found', 'error')
        return redirect(url_for('timesheet.index'))
    
    days = pay_period.get_days()
    entries = TimesheetEntry.get_by_period_and_employee(period_id, employee.name)
    
    # Convert entries to a dictionary for easier lookup
    entries_dict = {entry.day: entry for entry in entries}
    
    # Calculate totals
    totals = TimesheetEntry.get_total_hours_for_period(period_id, employee.name)
    
    return render_template(
        'timesheet/view.html',
        pay_period=pay_period,
        employee=employee,
        days=days,
        entries_dict=entries_dict,
        totals=totals,
        format_date=format_date
    )

@timesheet.route('/save', methods=['POST'])
def save():
    """Save a timesheet entry"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    period_id = data.get('period_id')
    employee_id = data.get('employee_id')
    day = data.get('day')
    hours = data.get('hours', '')
    pay = data.get('pay', '')
    project_name = data.get('project_name', '')
    install_days = data.get('install_days', '')
    install = data.get('install', '')
    reimbursement = data.get('reimbursement', '')
    
    # Validate required fields
    if not all([period_id, employee_id, day]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    # Get employee to get the name
    employee = Employee.get_by_id(employee_id)
    if not employee:
        return jsonify({'success': False, 'error': 'Employee not found'}), 404
    
    # Get existing entry or create new one
    entry = TimesheetEntry.get_by_date(period_id, employee.name, day)
    
    if entry:
        # Update existing entry
        entry.hours = hours
        entry.pay = pay
        entry.project_name = project_name
        entry.install_days = install_days
        entry.install = install
        entry.reimbursement = reimbursement
    else:
        # Create new entry
        entry = TimesheetEntry(
            employee_name=employee.name,
            period_id=period_id,
            day=day,
            hours=hours,
            pay=pay,
            project_name=project_name,
            install_days=install_days,
            install=install,
            reimbursement=reimbursement
        )
    
    # Save to database
    entry.save()
    
    # Calculate new totals
    total_hours = TimesheetEntry.get_total_hours_for_period(period_id, employee.name)
    
    return jsonify({
        'success': True, 
        'entry_id': entry.id,
        'total_hours': total_hours
    })

@timesheet.route('/api/entries/<period_id>/<employee_id>', methods=['GET'])
def api_entries(period_id, employee_id):
    """API endpoint to get all timesheet entries for a specific pay period and employee"""
    employee = Employee.get_by_id(employee_id)
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404
        
    entries = TimesheetEntry.get_by_period_and_employee(period_id, employee.name)
    return jsonify([entry.to_dict() for entry in entries])

@timesheet.route('/api/totals/<period_id>/<employee_id>', methods=['GET'])
def api_totals(period_id, employee_id):
    """API endpoint to get total hours for a specific pay period and employee"""
    employee = Employee.get_by_id(employee_id)
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404
        
    total_hours = TimesheetEntry.get_total_hours_for_period(period_id, employee.name)
    
    # Return total hours
    return jsonify({'total_hours': total_hours}) 