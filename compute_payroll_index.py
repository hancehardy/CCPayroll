import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
import matplotlib.pyplot as plt

# Path to the Excel file
excel_file = os.path.join('Local Docs', 'PAYROLL 2025.xlsx')

def extract_date_range(sheet_name):
    """Extract start and end dates from sheet name."""
    match = re.search(r'(\d+\.\d+\.\d+)\s+[Tt][Oo]\s+(\d+\.\d+\.\d+)', sheet_name)
    if match:
        start_date_str, end_date_str = match.groups()
        return start_date_str, end_date_str
    return None, None

def compute_indices():
    """Compute various payroll indices."""
    print("Reading Excel file:", excel_file)
    
    # Get all sheet names
    xl = pd.ExcelFile(excel_file)
    sheet_names = xl.sheet_names
    
    # Skip the first sheet which is a template
    sheet_names = [sheet for sheet in sheet_names if sheet != 'PAYROLL TIMESHEET']
    
    # Sort sheets by date
    def extract_date(sheet_name):
        start_date, _ = extract_date_range(sheet_name)
        if start_date:
            try:
                return datetime.strptime(start_date, '%m.%d.%y')
            except ValueError:
                pass
        return datetime(2025, 1, 1)  # Default date
    
    sheet_names.sort(key=extract_date)
    
    # Initialize data structures for indices
    all_employees = set()
    employee_pay_by_period = {}
    period_totals = {}
    
    # First pass: identify all employees
    for sheet in sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet)
        
        # Find employee names (they are typically in the first column)
        for idx, value in enumerate(df.iloc[:, 0]):
            if pd.notna(value) and isinstance(value, str) and value.strip().upper() == value.strip() and len(value.strip()) > 3 and value.strip() not in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY', 'DAY', 'DATE', 'CREATIVE CLOSETS PAYROLL TIME SHEET']:
                all_employees.add(value.strip())
    
    print(f"\nIdentified {len(all_employees)} employees:")
    for emp in sorted(all_employees):
        print(f"  - {emp}")
        employee_pay_by_period[emp] = []
    
    # Second pass: extract pay data for each employee in each period
    for sheet in sheet_names:
        print(f"\nProcessing pay period: {sheet}")
        df = pd.read_excel(excel_file, sheet_name=sheet)
        
        period_total = 0
        period_data = {}
        
        # Find the PAY column
        pay_col_idx = None
        for col_idx, col_name in enumerate(df.iloc[1]):
            if pd.notna(col_name) and isinstance(col_name, str) and 'PAY' in col_name.upper():
                pay_col_idx = col_idx
                break
        
        if pay_col_idx is None:
            print(f"  Warning: Could not find PAY column in sheet {sheet}")
            continue
        
        # Process each employee
        for employee in all_employees:
            employee_rows = []
            employee_found = False
            
            # Find rows for this employee
            for idx, row in df.iterrows():
                if pd.notna(row.iloc[0]) and isinstance(row.iloc[0], str) and row.iloc[0].strip() == employee:
                    employee_found = True
                elif employee_found and pd.notna(row.iloc[0]) and isinstance(row.iloc[0], str) and row.iloc[0].strip() in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']:
                    employee_rows.append(row)
                elif employee_found and pd.notna(row.iloc[0]) and isinstance(row.iloc[0], str) and row.iloc[0].strip().upper() == row.iloc[0].strip() and len(row.iloc[0].strip()) > 3 and row.iloc[0].strip() not in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY', 'DAY', 'DATE']:
                    # Found next employee
                    employee_found = False
            
            # Calculate total pay for this employee in this period
            employee_total_pay = 0
            for row in employee_rows:
                if pd.notna(row.iloc[pay_col_idx]) and row.iloc[pay_col_idx] != '':
                    try:
                        pay = float(row.iloc[pay_col_idx])
                        employee_total_pay += pay
                    except (ValueError, TypeError):
                        pass
            
            print(f"  {employee}: ${employee_total_pay:.2f}")
            
            # Store employee pay for this period
            employee_pay_by_period[employee].append({
                'Period': sheet,
                'Pay': employee_total_pay
            })
            
            period_data[employee] = employee_total_pay
            period_total += employee_total_pay
        
        period_data['Total'] = period_total
        period_totals[sheet] = period_data
    
    # Calculate indices
    print("\n===== PAYROLL INDICES =====")
    
    # 1. Total Pay Index
    print("\n1. TOTAL PAY BY EMPLOYEE")
    employee_total_pay = {}
    for employee in all_employees:
        total_pay = sum(period['Pay'] for period in employee_pay_by_period[employee])
        employee_total_pay[employee] = total_pay
    
    for employee, total_pay in sorted(employee_total_pay.items(), key=lambda x: x[1], reverse=True):
        print(f"{employee}: ${total_pay:.2f}")
    
    # 2. Pay Trend Index
    print("\n2. PAY TREND OVER TIME")
    for employee in sorted(all_employees):
        if not any(period['Pay'] > 0 for period in employee_pay_by_period[employee]):
            continue  # Skip employees with no pay
            
        print(f"\n{employee} Pay Trend:")
        periods = [p['Period'] for p in employee_pay_by_period[employee]]
        pays = [p['Pay'] for p in employee_pay_by_period[employee]]
        
        # Find first non-zero pay as base
        base_pay = next((pay for pay in pays if pay > 0), 1)
        if base_pay > 0:
            trend_indices = [(pay / base_pay) * 100 if pay > 0 else 0 for pay in pays]
            for i, period in enumerate(periods):
                if pays[i] > 0:
                    print(f"  {period}: ${pays[i]:.2f} (Index: {trend_indices[i]:.1f})")
    
    # 3. Relative Pay Index (comparing employees)
    print("\n3. RELATIVE PAY INDEX (COMPARING EMPLOYEES)")
    non_zero_employees = {emp: pay for emp, pay in employee_total_pay.items() if pay > 0}
    if non_zero_employees:
        # Find the employee with highest total pay as the baseline
        max_pay_employee = max(non_zero_employees.items(), key=lambda x: x[1])
        max_pay = max_pay_employee[1]
        
        if max_pay > 0:
            print(f"Baseline: {max_pay_employee[0]} (${max_pay:.2f}, Index: 100.0)")
            for employee, total_pay in sorted(non_zero_employees.items(), key=lambda x: x[1], reverse=True):
                if employee != max_pay_employee[0] and total_pay > 0:
                    relative_index = (total_pay / max_pay) * 100
                    print(f"{employee}: ${total_pay:.2f} (Index: {relative_index:.1f})")
    
    # 4. Period-over-Period Change Index
    print("\n4. PERIOD-OVER-PERIOD CHANGE INDEX")
    for employee in sorted(all_employees):
        pays = [p['Pay'] for p in employee_pay_by_period[employee]]
        if len(pays) < 2 or not any(pay > 0 for pay in pays):
            continue
            
        print(f"\n{employee} Period-over-Period Change:")
        periods = [p['Period'] for p in employee_pay_by_period[employee]]
        
        for i in range(1, len(pays)):
            if pays[i-1] > 0 and pays[i] > 0:
                change_pct = ((pays[i] - pays[i-1]) / pays[i-1]) * 100
                print(f"  {periods[i-1]} to {periods[i]}: ${pays[i-1]:.2f} → ${pays[i]:.2f} (Change: {change_pct:+.1f}%)")
    
    # Generate visualizations
    try:
        # Create a directory for visualizations if it doesn't exist
        if not os.path.exists('payroll_analysis'):
            os.makedirs('payroll_analysis')
        
        # Filter to employees with non-zero pay
        active_employees = [emp for emp in all_employees if employee_total_pay[emp] > 0]
        
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
            plt.savefig('payroll_analysis/total_pay_by_employee.png')
            
            # 2. Pay Trend Over Time
            plt.figure(figsize=(12, 6))
            for employee in active_employees:
                periods = [p['Period'] for p in employee_pay_by_period[employee]]
                pays = [p['Pay'] for p in employee_pay_by_period[employee]]
                if any(pay > 0 for pay in pays):
                    plt.plot(range(len(periods)), pays, marker='o', label=employee)
            
            plt.title('Pay Trend Over Time')
            plt.xlabel('Pay Period')
            plt.ylabel('Pay Amount ($)')
            plt.xticks(range(len(sheet_names)), [s.replace('payroll ', '') for s in sheet_names], rotation=45, ha='right')
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig('payroll_analysis/pay_trend_over_time.png')
            
            # 3. Total Payroll by Period
            plt.figure(figsize=(12, 6))
            period_sums = [sum(period_totals[sheet][emp] for emp in active_employees if emp in period_totals[sheet]) for sheet in sheet_names]
            plt.bar(range(len(sheet_names)), period_sums)
            plt.title('Total Payroll by Period')
            plt.xlabel('Pay Period')
            plt.ylabel('Total Payroll ($)')
            plt.xticks(range(len(sheet_names)), [s.replace('payroll ', '') for s in sheet_names], rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig('payroll_analysis/total_payroll_by_period.png')
            
            print("\nVisualizations saved in 'payroll_analysis' directory.")
        else:
            print("\nNo active employees with pay found. Skipping visualizations.")
    except Exception as e:
        print(f"Error generating visualizations: {e}")
    
    return employee_total_pay, employee_pay_by_period, period_totals

if __name__ == "__main__":
    try:
        employee_total_pay, employee_pay_by_period, period_totals = compute_indices()
        print("\nPayroll index computation completed successfully.")
    except Exception as e:
        print(f"Error computing payroll indices: {e}") 