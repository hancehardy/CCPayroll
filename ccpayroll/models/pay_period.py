"""
PayPeriod model for Creative Closets Payroll
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from ..database import get_db

@dataclass
class PayPeriod:
    """Pay period model representing a specific pay timeframe"""
    name: str
    start_date: str  # YYYY-MM-DD format
    end_date: str    # YYYY-MM-DD format
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pay period to dictionary for database storage"""
        return {
            'id': self.id,
            'name': self.name,
            'start_date': self.start_date,
            'end_date': self.end_date
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PayPeriod':
        """Create a PayPeriod instance from a dictionary"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data['name'],
            start_date=data['start_date'],
            end_date=data['end_date']
        )
    
    @classmethod
    def get_all(cls) -> List['PayPeriod']:
        """Get all pay periods from the database, ordered by start date descending"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM pay_periods ORDER BY start_date DESC')
            rows = cursor.fetchall()
        
        return [cls.from_dict(dict(row)) for row in rows]
    
    @classmethod
    def get_by_id(cls, period_id: str) -> Optional['PayPeriod']:
        """Get a pay period by ID"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM pay_periods WHERE id = %s', (period_id,))
            row = cursor.fetchone()
        
        return cls.from_dict(dict(row)) if row else None
    
    def save(self) -> None:
        """Save this pay period to the database"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO pay_periods (id, name, start_date, end_date) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date
                ''',
                (self.id, self.name, self.start_date, self.end_date)
            )
            conn.commit()
    
    def delete(self) -> None:
        """Delete this pay period and all associated timesheet entries"""
        with get_db() as conn:
            try:
                cursor = conn.cursor()
                
                # First, get all timesheet entries associated with this period
                cursor.execute('SELECT id FROM timesheet_entries WHERE period_id = %s', (self.id,))
                timesheet_entry_ids = [row['id'] for row in cursor.fetchall()]
                
                # Delete each timesheet entry individually
                for entry_id in timesheet_entry_ids:
                    cursor.execute('DELETE FROM timesheet_entries WHERE id = %s', (entry_id,))
                
                # Now delete the pay period
                cursor.execute('DELETE FROM pay_periods WHERE id = %s', (self.id,))
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise Exception(f"Failed to delete pay period: {str(e)}")
    
    def get_days(self) -> List[Dict[str, str]]:
        """Get all days in this pay period as a list of day objects"""
        days = []
        start = datetime.strptime(self.start_date, '%Y-%m-%d')
        end = datetime.strptime(self.end_date, '%Y-%m-%d')
        
        current = start
        while current <= end:
            days.append({
                'date': current.strftime('%Y-%m-%d'),
                'day': current.strftime('%A').upper()
            })
            current += timedelta(days=1)
        
        return days
    
    @staticmethod
    def generate_name_from_dates(start_date: str, end_date: str) -> str:
        """Generate a pay period name from start and end dates"""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            return f"{start.strftime('%m/%d/%y')} to {end.strftime('%m/%d/%y')}"
        except ValueError:
            # Fallback to current date if dates are invalid
            return f"Pay Period {datetime.now().strftime('%m/%d/%y')}" 