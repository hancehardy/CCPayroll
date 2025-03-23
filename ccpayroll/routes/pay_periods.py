"""
Pay Period routes for Creative Closets Payroll

This module handles pay period-related routes, including listing, adding, editing, and deleting pay periods.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..models import PayPeriod
from ..utils import generate_pay_period_dates, parse_date

pay_periods = Blueprint('pay_periods', __name__, url_prefix='/pay-periods')

@pay_periods.route('/')
def index():
    """Display all pay periods"""
    all_periods = PayPeriod.get_all()
    return render_template('pay_periods/index.html', pay_periods=all_periods)

@pay_periods.route('/add', methods=['GET', 'POST'])
def add():
    """Add a new pay period"""
    if request.method == 'POST':
        # Process form data
        name = request.form.get('name', '').strip()
        start_date = parse_date(request.form.get('start_date', ''))
        end_date = parse_date(request.form.get('end_date', ''))
        
        # Validate required fields
        if not name or not start_date or not end_date:
            flash('All fields are required', 'error')
            return render_template('pay_periods/add.html')
        
        # Create pay period object
        pay_period = PayPeriod(
            name=name,
            start_date=start_date,
            end_date=end_date
        )
        
        # Save to database
        pay_period.save()
        
        flash(f'Pay period {name} added successfully', 'success')
        return redirect(url_for('pay_periods.index'))
    
    # GET request - show add form with suggested dates
    start_date, end_date = generate_pay_period_dates()
    suggested_name = PayPeriod.generate_name_from_dates(start_date, end_date)
    
    return render_template('pay_periods/add.html', 
                          start_date=start_date, 
                          end_date=end_date,
                          name=suggested_name)

@pay_periods.route('/edit/<period_id>', methods=['GET', 'POST'])
def edit(period_id):
    """Edit an existing pay period"""
    pay_period = PayPeriod.get_by_id(period_id)
    if not pay_period:
        flash('Pay period not found', 'error')
        return redirect(url_for('pay_periods.index'))
    
    if request.method == 'POST':
        # Process form data
        pay_period.name = request.form.get('name', '').strip()
        pay_period.start_date = parse_date(request.form.get('start_date', ''))
        pay_period.end_date = parse_date(request.form.get('end_date', ''))
        
        # Validate required fields
        if not pay_period.name or not pay_period.start_date or not pay_period.end_date:
            flash('All fields are required', 'error')
            return render_template('pay_periods/edit.html', pay_period=pay_period)
        
        # Save to database
        pay_period.save()
        
        flash(f'Pay period {pay_period.name} updated successfully', 'success')
        return redirect(url_for('pay_periods.index'))
    
    # GET request - show edit form
    return render_template('pay_periods/edit.html', pay_period=pay_period)

@pay_periods.route('/delete/<period_id>', methods=['POST'])
def delete(period_id):
    """Delete a pay period"""
    pay_period = PayPeriod.get_by_id(period_id)
    if not pay_period:
        flash('Pay period not found', 'error')
        return redirect(url_for('pay_periods.index'))
    
    period_name = pay_period.name
    pay_period.delete()
    
    flash(f'Pay period {period_name} deleted successfully', 'success')
    return redirect(url_for('pay_periods.index'))

@pay_periods.route('/api/list', methods=['GET'])
def api_list():
    """API endpoint to get all pay periods as JSON"""
    all_periods = PayPeriod.get_all()
    return jsonify([period.to_dict() for period in all_periods])

@pay_periods.route('/api/<period_id>', methods=['GET'])
def api_get(period_id):
    """API endpoint to get a specific pay period as JSON"""
    pay_period = PayPeriod.get_by_id(period_id)
    if not pay_period:
        return jsonify({'error': 'Pay period not found'}), 404
    
    return jsonify(pay_period.to_dict())

@pay_periods.route('/api/suggest', methods=['GET'])
def api_suggest():
    """API endpoint to get suggested dates for a new pay period"""
    start_date, end_date = generate_pay_period_dates()
    name = PayPeriod.generate_name_from_dates(start_date, end_date)
    
    return jsonify({
        'start_date': start_date,
        'end_date': end_date,
        'name': name
    }) 