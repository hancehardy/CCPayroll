"""
Employee model for Creative Closets Payroll
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional, ClassVar, Dict, Any
from ..database import get_db

@dataclass
class Employee:
    """Employee model represents a person working at Creative Closets"""
    name: str
    position: str = "none"
    install_crew: int = 0
    pay_type: str = "hourly"
    rate: Optional[float] = None
    salary: Optional[float] = None
    commission_rate: Optional[float] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert employee to dictionary for database storage"""
        return {
            'id': self.id,
            'name': self.name,
            'position': self.position,
            'install_crew': self.install_crew,
            'pay_type': self.pay_type,
            'rate': self.rate,
            'salary': self.salary,
            'commission_rate': self.commission_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Employee':
        """Create an Employee instance from a dictionary"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data['name'],
            position=data.get('position', 'none'),
            install_crew=int(data.get('install_crew', 0)),
            pay_type=data.get('pay_type', 'hourly'),
            rate=float(data['rate']) if data.get('rate') else None,
            salary=float(data['salary']) if data.get('salary') else None,
            commission_rate=float(data['commission_rate']) if data.get('commission_rate') else None
        )
    
    @classmethod
    def get_all(cls) -> list['Employee']:
        """Get all employees from the database"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM employees ORDER BY name')
            rows = cursor.fetchall()
        
        return [cls.from_dict(dict(row)) for row in rows]
    
    @classmethod
    def get_by_id(cls, employee_id: str) -> Optional['Employee']:
        """Get an employee by ID"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Check if PostgreSQL connection
            if hasattr(conn, '_con') and conn._con.__class__.__module__.startswith('psycopg2'):
            else:
                cursor.execute('SELECT * FROM employees WHERE id = ?', (employee_id,))
                
            row = cursor.fetchone()
        
        return cls.from_dict(dict(row)) if row else None
    
    @classmethod
    def get_by_name(cls, name: str) -> Optional['Employee']:
        """Get an employee by name"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Check if PostgreSQL connection
            if hasattr(conn, '_con') and conn._con.__class__.__module__.startswith('psycopg2'):
            else:
                cursor.execute('SELECT * FROM employees WHERE name = ?', (name,))
                
            row = cursor.fetchone()
        
        return cls.from_dict(dict(row)) if row else None
    
    def save(self) -> None:
        """Save this employee to the database"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Check if PostgreSQL connection
            if hasattr(conn, '_con') and conn._con.__class__.__module__.startswith('psycopg2'):
                # PostgreSQL syntax
                cursor.execute(
                    '''
                    INSERT INTO employees (
                        id, name, rate, install_crew, position, 
                        pay_type, salary, commission_rate
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        rate = EXCLUDED.rate,
                        install_crew = EXCLUDED.install_crew,
                        position = EXCLUDED.position,
                        pay_type = EXCLUDED.pay_type,
                        salary = EXCLUDED.salary,
                        commission_rate = EXCLUDED.commission_rate
                    ''',
                    (
                        self.id, 
                        self.name, 
                        self.rate, 
                        self.install_crew, 
                        self.position,
                        self.pay_type,
                        self.salary,
                        self.commission_rate
                    )
                )
            else:
                # SQLite syntax
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO employees (
                        id, name, rate, install_crew, position, 
                        pay_type, salary, commission_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        self.id, 
                        self.name, 
                        self.rate, 
                        self.install_crew, 
                        self.position,
                        self.pay_type,
                        self.salary,
                        self.commission_rate
                    )
                )
            
            conn.commit()
    
    def delete(self) -> None:
        """Delete this employee from the database"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM employees WHERE id = ?', (self.id,))
            conn.commit()
    
    def calculate_pay(self, regular_hours: float, overtime_hours: float = 0) -> Dict[str, float]:
        """Calculate pay based on hours and pay type
        
        Args:
            regular_hours: Regular hours worked
            overtime_hours: Overtime hours worked (optional)
            
        Returns:
            Dictionary with regular_pay, overtime_pay, and total_pay
        """
        regular_pay = 0.0
        overtime_pay = 0.0
        
        if self.pay_type == 'hourly' and self.rate:
            regular_pay = regular_hours * self.rate
            overtime_pay = overtime_hours * self.rate * 1.5
        elif self.pay_type == 'salary' and self.salary:
            # Weekly salary (annual / 52)
            regular_pay = self.salary / 52
            overtime_pay = 0.0
        
        total_pay = regular_pay + overtime_pay
        
        return {
            'regular': regular_pay,
            'overtime': overtime_pay,
            'total': total_pay
        }
