"""
Reports module for Creative Closets Payroll

This module provides report generation functionality.
"""

import os
import csv
import pandas as pd
from typing import List, Dict, Any
from io import StringIO
from flask import render_template
import pdfkit
from datetime import datetime

from ..models import Employee, PayPeriod, TimesheetEntry
from ..utils import format_currency, format_date

def generate_payroll_report(period_id: str) -> str:
    """Generate a payroll report for a specific pay period
    
    Args:
        period_id: The ID of the pay period
        
    Returns:
        Path to the generated PDF file
    """
    period = PayPeriod.get_by_id(period_id)
    if not period:
        raise ValueError(f"Pay period with ID {period_id} not found")
        
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
    
    # Generate HTML report
    html = render_template(
        'reports/payroll.html',
        period=period,
        employees=report_data,
        format_currency=format_currency,
        format_date=format_date,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    # Create reports directory if it doesn't exist
    report_dir = os.path.join(os.getcwd(), 'reports')
    os.makedirs(report_dir, exist_ok=True)
    
    # Generate PDF
    filename = f"payroll_{period.start_date}_to_{period.end_date}.pdf"
    filepath = os.path.join(report_dir, filename)
    
    pdfkit.from_string(html, filepath)
    
    return filepath

def generate_timesheet_csv(period_id: str, employee_id: str = None) -> str:
    """Generate a CSV timesheet report
    
    Args:
        period_id: The ID of the pay period
        employee_id: Optional employee ID to filter results
        
    Returns:
        Path to the generated CSV file
    """
    period = PayPeriod.get_by_id(period_id)
    if not period:
        raise ValueError(f"Pay period with ID {period_id} not found")
    
    # Create reports directory if it doesn't exist
    report_dir = os.path.join(os.getcwd(), 'reports')
    os.makedirs(report_dir, exist_ok=True)
    
    # Determine filename based on whether filtering by employee
    if employee_id:
        employee = Employee.get_by_id(employee_id)
        if not employee:
            raise ValueError(f"Employee with ID {employee_id} not found")
        filename = f"timesheet_{employee.name.replace(' ', '_')}_{period.start_date}_to_{period.end_date}.csv"
    else:
        filename = f"timesheet_all_{period.start_date}_to_{period.end_date}.csv"
    
    filepath = os.path.join(report_dir, filename)
    
    # Collect all timesheet entries
    data = []
    
    # Get employees to include in report
    if employee_id:
        employees = [Employee.get_by_id(employee_id)]
    else:
        employees = Employee.get_all()
    
    # Collect timesheet data
    for employee in employees:
        entries = TimesheetEntry.get_by_period_and_employee(period_id, employee.id)
        
        for entry in entries:
            pay_amount = entry.pay
            
            # If this is a salaried employee and no pay is set, calculate it
            if employee.pay_type == 'salary' and employee.salary and (not pay_amount or pay_amount.strip() == ''):
                pay_amount = str(round(employee.salary / 52, 2))
                
            data.append({
                'Employee': employee.name,
                'Position': employee.position,
                'Date': format_date(entry.date),
                'Regular Hours': entry.regular_hours,
                'Overtime Hours': entry.overtime_hours,
                'Job': entry.job_name,
                'Notes': entry.notes,
                'Pay': pay_amount
            })
    
    # Create a DataFrame and sort by Employee and Date
    if data:
        df = pd.DataFrame(data)
        df.sort_values(['Employee', 'Date'], inplace=True)
        df.to_csv(filepath, index=False)
    else:
        # Create empty CSV with headers if no data
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Employee', 'Position', 'Date', 'Regular Hours', 
                            'Overtime Hours', 'Job', 'Notes', 'Pay'])
    
    return filepath 