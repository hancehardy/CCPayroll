"""
Utilities module for Creative Closets Payroll

This module provides utility functions used throughout the application.
"""

from datetime import datetime, timedelta

def format_currency(value: float) -> str:
    """Format a float value as currency string"""
    return f"${value:.2f}"

def format_date(date_str: str, output_format: str = '%m/%d/%Y') -> str:
    """Format a date string to another format
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        output_format: Desired output format
        
    Returns:
        Formatted date string
    """
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime(output_format)
    except (ValueError, TypeError):
        return date_str
    
def parse_date(date_str: str, input_format: str = '%m/%d/%Y') -> str:
    """Parse a date string to YYYY-MM-DD format
    
    Args:
        date_str: Date string in the input format
        input_format: Input date format
        
    Returns:
        Date string in YYYY-MM-DD format
    """
    try:
        date_obj = datetime.strptime(date_str, input_format)
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return date_str

def generate_pay_period_dates(reference_date: str = None) -> tuple:
    """Generate start and end dates for a new pay period
    
    By default, creates a pay period for the most recent complete two-week period,
    ending on the previous Saturday.
    
    Args:
        reference_date: Optional reference date in YYYY-MM-DD format
        
    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    if reference_date:
        ref_date = datetime.strptime(reference_date, '%Y-%m-%d')
    else:
        ref_date = datetime.now()
    
    # Find the most recent Saturday
    days_since_saturday = (ref_date.weekday() + 2) % 7  # Saturday is 5, we want to make it 0
    last_saturday = ref_date - timedelta(days=days_since_saturday)
    
    # Pay period is two weeks, so start date is 13 days before end date
    end_date = last_saturday
    start_date = end_date - timedelta(days=13)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d') 