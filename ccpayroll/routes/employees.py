"""
Employee routes for Creative Closets Payroll

This module handles employee-related routes, including listing, adding, editing, and deleting employees.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..models import Employee

employees = Blueprint('employees', __name__, url_prefix='/employees')

@employees.route('/')
def index():
    """Display all employees"""
    all_employees = Employee.get_all()
    return render_template('employees/index.html', employees=all_employees)

@employees.route('/add', methods=['GET', 'POST'])
def add():
    """Add a new employee"""
    if request.method == 'POST':
        # Process form data
        name = request.form.get('name', '').strip()
        position = request.form.get('position', '').strip()
        pay_type = request.form.get('pay_type', 'hourly')
        rate = float(request.form.get('rate', 0))
        salary = float(request.form.get('salary', 0))
        commission_rate = float(request.form.get('commission_rate', 0))
        install_crew = request.form.get('install_crew', 'off') == 'on'
        
        # Validate required fields
        if not name:
            flash('Employee name is required', 'error')
            return render_template('employees/add.html')
        
        # Create employee object
        employee = Employee(
            name=name,
            position=position,
            pay_type=pay_type,
            rate=rate,
            salary=salary,
            commission_rate=commission_rate,
            install_crew=install_crew
        )
        
        # Save to database
        employee.save()
        
        flash(f'Employee {name} added successfully', 'success')
        return redirect(url_for('employees.index'))
    
    # GET request - show add form
    return render_template('employees/add.html')

@employees.route('/edit/<employee_id>', methods=['GET', 'POST'])
def edit(employee_id):
    """Edit an existing employee"""
    employee = Employee.get_by_id(employee_id)
    if not employee:
        flash('Employee not found', 'error')
        return redirect(url_for('employees.index'))
    
    if request.method == 'POST':
        # Process form data
        employee.name = request.form.get('name', '').strip()
        employee.position = request.form.get('position', '').strip()
        employee.pay_type = request.form.get('pay_type', 'hourly')
        employee.rate = float(request.form.get('rate', 0))
        employee.salary = float(request.form.get('salary', 0))
        employee.commission_rate = float(request.form.get('commission_rate', 0))
        employee.install_crew = request.form.get('install_crew', 'off') == 'on'
        
        # Validate required fields
        if not employee.name:
            flash('Employee name is required', 'error')
            return render_template('employees/edit.html', employee=employee)
        
        # Save to database
        employee.save()
        
        flash(f'Employee {employee.name} updated successfully', 'success')
        return redirect(url_for('employees.index'))
    
    # GET request - show edit form
    return render_template('employees/edit.html', employee=employee)

@employees.route('/delete/<employee_id>', methods=['POST'])
def delete(employee_id):
    """Delete an employee"""
    employee = Employee.get_by_id(employee_id)
    if not employee:
        flash('Employee not found', 'error')
        return redirect(url_for('employees.index'))
    
    employee_name = employee.name
    employee.delete()
    
    flash(f'Employee {employee_name} deleted successfully', 'success')
    return redirect(url_for('employees.index'))

@employees.route('/api/list', methods=['GET'])
def api_list():
    """API endpoint to get all employees as JSON"""
    all_employees = Employee.get_all()
    return jsonify([emp.to_dict() for emp in all_employees])

@employees.route('/api/<employee_id>', methods=['GET'])
def api_get(employee_id):
    """API endpoint to get a specific employee as JSON"""
    employee = Employee.get_by_id(employee_id)
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404
    
    return jsonify(employee.to_dict()) 