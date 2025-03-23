"""
Routes module for Creative Closets Payroll

This module provides all the Flask route blueprints for the application.
"""

from .main import main
from .employees import employees
from .pay_periods import pay_periods
from .timesheet import timesheet
from .reports import reports

__all__ = ['main', 'employees', 'pay_periods', 'timesheet', 'reports'] 