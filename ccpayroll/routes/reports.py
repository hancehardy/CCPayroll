"""
Reports routes for Creative Closets Payroll

This module handles report generation and viewing routes.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from ..models import Employee, PayPeriod, TimesheetEntry
from ..reports import generate_payroll_report, generate_timesheet_csv

reports = Blueprint('reports', __name__, url_prefix='/reports')

@reports.route('/')
def index():
    """Display report selection page"""
    pay_periods = PayPeriod.get_all()
    employees = Employee.get_all()
    
    return render_template(
        'reports/index.html',
        pay_periods=pay_periods,
        employees=employees
    )

@reports.route('/payroll/<period_id>')
def payroll(period_id):
    """Generate payroll report for a specific pay period"""
    pay_period = PayPeriod.get_by_id(period_id)
    if not pay_period:
        flash('Pay period not found', 'error')
        return redirect(url_for('reports.index'))
    
    try:
        # Generate the report PDF
        filepath = generate_payroll_report(period_id)
        
        # Send the file to the user
        return send_file(
            filepath,
            as_attachment=True,
            download_name=f"payroll_{pay_period.name.replace(' ', '_')}.pdf"
        )
    except Exception as e:
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('reports.index'))

@reports.route('/timesheet/<period_id>')
def timesheet(period_id):
    """Generate timesheet report for a specific pay period"""
    pay_period = PayPeriod.get_by_id(period_id)
    if not pay_period:
        flash('Pay period not found', 'error')
        return redirect(url_for('reports.index'))
    
    # Check if filtering by employee
    employee_id = request.args.get('employee_id')
    
    try:
        # Generate the report CSV
        filepath = generate_timesheet_csv(period_id, employee_id)
        
        # Send the file to the user
        filename = os.path.basename(filepath)
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('reports.index'))

@reports.route('/preview/payroll/<period_id>')
def preview_payroll(period_id):
    """Preview payroll report for a specific pay period"""
    pay_period = PayPeriod.get_by_id(period_id)
    if not pay_period:
        flash('Pay period not found', 'error')
        return redirect(url_for('reports.index'))
    
    employees = Employee.get_all()
    
    # Collect data for each employee
    report_data = []
    
    for employee in employees:
        hours = TimesheetEntry.get_total_hours_for_period(period_id, employee.id)
        pay_data = employee.calculate_pay(hours['regular'], hours['overtime'])
        
        report_data.append({
            'name': employee.name,
            'position': employee.position,
            'pay_type': employee.pay_type,
            'regular_hours': hours['regular'],
            'overtime_hours': hours['overtime'],
            'regular_pay': pay_data['regular'],
            'overtime_pay': pay_data['overtime'],
            'total_pay': pay_data['total']
        })
    
    return render_template(
        'reports/payroll.html',
        period=pay_period,
        employees=report_data,
        preview=True
    ) 