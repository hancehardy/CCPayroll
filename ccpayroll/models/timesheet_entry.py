"""
TimesheetEntry model for Creative Closets Payroll
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from ..database import get_db

@dataclass
class TimesheetEntry:
    """TimesheetEntry model representing a single day's work for an employee"""
    period_id: str
    employee_name: str
    day: str  # YYYY-MM-DD format
    hours: str = ""
    pay: str = ""
    project_name: str = ""
    install_days: str = ""
    install: str = ""
    regular_hours: float = 0.0
    overtime_hours: float = 0.0
    job_name: str = ""
    notes: str = ""
    reimbursement: str = ""
    id: int = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert timesheet entry to dictionary for database storage"""
        return {
            'id': self.id,
            'period_id': self.period_id,
            'employee_name': self.employee_name,
            'day': self.day,
            'hours': self.hours,
            'pay': self.pay,
            'project_name': self.project_name,
            'install_days': self.install_days,
            'install': self.install,
            'regular_hours': self.regular_hours,
            'overtime_hours': self.overtime_hours,
            'job_name': self.job_name,
            'notes': self.notes,
            'reimbursement': self.reimbursement
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimesheetEntry':
        """Create a TimesheetEntry instance from a dictionary"""
        return cls(
            id=data.get('id'),
            period_id=data['period_id'],
            employee_name=data['employee_name'],
            day=data['day'],
            hours=data.get('hours', ''),
            pay=data.get('pay', ''),
            project_name=data.get('project_name', ''),
            install_days=data.get('install_days', ''),
            install=data.get('install', ''),
            regular_hours=float(data.get('regular_hours', 0)),
            overtime_hours=float(data.get('overtime_hours', 0)),
            job_name=data.get('job_name', ''),
            notes=data.get('notes', ''),
            reimbursement=data.get('reimbursement', '')
        )
    
    @classmethod
    def get_by_period_and_employee(cls, period_id: str, employee_id: str) -> List['TimesheetEntry']:
        """Get all timesheet entries for a specific pay period and employee"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM timesheet_entries WHERE period_id = %s AND employee_name = %s ORDER BY day',
                (period_id, employee_id)
            )
            rows = cursor.fetchall()
        
        return [cls.from_dict(dict(row)) for row in rows]
    
    @classmethod
    def get_by_date(cls, period_id: str, employee_id: str, date: str) -> Optional['TimesheetEntry']:
        """Get a timesheet entry for a specific date, period, and employee"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM timesheet_entries WHERE period_id = %s AND employee_name = %s AND day = %s',
                (period_id, employee_id, date)
            )
            row = cursor.fetchone()
        
        return cls.from_dict(dict(row)) if row else None
    
    def save(self) -> None:
        """Save this timesheet entry to the database"""
        with get_db() as conn:
            cursor = conn.cursor()
            # If id is None, it's a new entry
            if self.id is None:
                cursor.execute(
                    '''
                    INSERT INTO timesheet_entries 
                    (period_id, employee_name, day, hours, pay, project_name, install_days, install, regular_hours, overtime_hours, job_name, notes, reimbursement) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    ''',
                    (
                        self.period_id, 
                        self.employee_name, 
                        self.day, 
                        self.hours, 
                        self.pay, 
                        self.project_name, 
                        self.install_days, 
                        self.install,
                        self.regular_hours,
                        self.overtime_hours,
                        self.job_name,
                        self.notes,
                        self.reimbursement
                    )
                )
                result = cursor.fetchone()
                self.id = result['id']
            else:
                cursor.execute(
                    '''
                    UPDATE timesheet_entries SET
                    period_id = %s, employee_name = %s, day = %s, hours = %s, pay = %s, 
                    project_name = %s, install_days = %s, install = %s, regular_hours = %s, overtime_hours = %s, job_name = %s, notes = %s, reimbursement = %s
                    WHERE id = %s
                    ''',
                    (
                        self.period_id, 
                        self.employee_name, 
                        self.day, 
                        self.hours, 
                        self.pay, 
                        self.project_name, 
                        self.install_days, 
                        self.install,
                        self.regular_hours,
                        self.overtime_hours,
                        self.job_name,
                        self.notes,
                        self.reimbursement,
                        self.id
                    )
                )
            conn.commit()
    
    def delete(self) -> None:
        """Delete this timesheet entry"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM timesheet_entries WHERE id = %s', (self.id,))
            conn.commit()
    
    @staticmethod
    def get_total_hours_for_period(period_id: str, employee_id: str) -> Dict[str, float]:
        """Get total hours for an employee in a pay period
        
        Returns a dictionary with 'hours' and 'pay'
        """
        total = {'hours': 0.0, 'pay': 0.0}
        
        entries = TimesheetEntry.get_by_period_and_employee(period_id, employee_id)
        
        for entry in entries:
            # Add hours
            if entry.hours and entry.hours.strip():
                try:
                    total['hours'] += float(entry.hours)
                except (ValueError, TypeError):
                    pass
            
            # Add pay
            if entry.pay and entry.pay.strip():
                try:
                    total['pay'] += float(entry.pay)
                except (ValueError, TypeError):
                    pass
        
        return total 