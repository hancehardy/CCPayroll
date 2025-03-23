"""
Main routes for Creative Closets Payroll

This module handles the main application routes, including the dashboard.
"""

from flask import Blueprint, render_template, redirect, url_for
from ..models import Employee, PayPeriod, TimesheetEntry

main = Blueprint('main', __name__)

@main.route('/')
def index():
    """Render the application dashboard"""
    # Get pay periods ordered by date
    pay_periods = PayPeriod.get_all()
    
    # Get all employees for display
    employees = Employee.get_all()
    
    # Get current period (first in the list if exists)
    current_period = pay_periods[0] if pay_periods else None
    
    # Dashboard statistics
    stats = {
        'total_employees': len(employees),
        'total_periods': len(pay_periods),
    }
    
    # If we have a current period, add period-specific stats
    if current_period:
        period_stats = {
            'period_name': current_period.name,
            'total_entries': 0,
            'total_hours': 0
        }
        
        # Calculate totals for current period
        for employee in employees:
            total_hours = TimesheetEntry.get_total_hours_for_period(current_period.id, employee.name)
            period_stats['total_hours'] += total_hours
            
            # Count entries for this employee
            entries = TimesheetEntry.get_by_period_and_employee(current_period.id, employee.name)
            period_stats['total_entries'] += len(entries)
        
        stats.update(period_stats)
    
    return render_template(
        'index.html', 
        employees=employees,
        pay_periods=pay_periods, 
        current_period=current_period,
        stats=stats
    ) 