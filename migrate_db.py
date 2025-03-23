#!/usr/bin/env python3
"""
Database Migration Script: SQLite to PostgreSQL

This script migrates data from a SQLite database to a PostgreSQL database.
It is designed for use in a Heroku environment but can be run locally with proper configuration.

Usage:
    python migrate_db.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (provided by Heroku)
    LOG_LEVEL: Logging level (default: INFO)
"""

import os
import sys
import sqlite3
import logging
import datetime
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from contextlib import contextmanager

# Load environment variables from .env file if exists
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("db_migration")

# Database paths
SQLITE_DB_PATH = os.path.join("data", "payroll.db")
# Get PostgreSQL connection string from environment variable
POSTGRES_URL = os.getenv("DATABASE_URL")

if not POSTGRES_URL:
    logger.error("DATABASE_URL environment variable not set. Exiting.")
    sys.exit(1)

# Type mapping from SQLite to PostgreSQL
TYPE_MAPPING = {
    "INTEGER": "INTEGER",
    "REAL": "FLOAT",
    "TEXT": "TEXT",
    "BLOB": "BYTEA"
}

# Special type mapping for known columns (overrides the general mapping)
COLUMN_TYPE_MAPPING = {
    "id": "TEXT",
    "period_id": "TEXT",
    "employee_name": "TEXT",
    "pay_periods.id": "TEXT PRIMARY KEY",
    "employees.id": "TEXT PRIMARY KEY",
    "timesheet_entries.id": "SERIAL PRIMARY KEY"
}

@contextmanager
def sqlite_connection():
    """Context manager for SQLite database connection"""
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"SQLite database file not found: {SQLITE_DB_PATH}")
        sys.exit(1)
        
    conn = None
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"SQLite connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

@contextmanager
def postgres_connection():
    """Context manager for PostgreSQL database connection"""
    conn = None
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        yield conn
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_sqlite_tables():
    """Get all table names from SQLite database"""
    with sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        return [row[0] for row in cursor.fetchall()]

def get_table_schema(table_name):
    """Get the schema for a specific table from SQLite"""
    with sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return cursor.fetchall()

def map_column_type(column_name, sqlite_type, table_name=None):
    """Map SQLite column type to PostgreSQL type"""
    # Check for specific column mappings
    full_column_name = f"{table_name}.{column_name}" if table_name else column_name
    if full_column_name in COLUMN_TYPE_MAPPING:
        return COLUMN_TYPE_MAPPING[full_column_name]
    if column_name in COLUMN_TYPE_MAPPING:
        return COLUMN_TYPE_MAPPING[column_name]
    
    # Handle default mappings
    for sqlite_keyword, pg_type in TYPE_MAPPING.items():
        if sqlite_keyword in sqlite_type.upper():
            return pg_type
    
    # Default to TEXT if no mapping found
    return "TEXT"

def create_postgres_tables(tables):
    """Create tables in PostgreSQL based on SQLite schema"""
    with postgres_connection() as conn:
        cursor = conn.cursor()
        
        # Process tables in correct order (handle foreign keys)
        # First 'pay_periods' (referenced by timesheet_entries)
        # Then 'employees'
        # Finally 'timesheet_entries'
        ordered_tables = []
        priority_tables = ['pay_periods', 'employees']
        
        for table in priority_tables:
            if table in tables:
                ordered_tables.append(table)
                tables.remove(table)
        
        ordered_tables.extend(tables)
        
        for table_name in ordered_tables:
            schema = get_table_schema(table_name)
            
            # Prepare column definitions
            columns = []
            primary_key = None
            
            for col in schema:
                col_name = col['name']
                col_type = col['type']
                not_null = col['notnull']
                pk = col['pk']
                default_value = col['dflt_value']
                
                pg_type = map_column_type(col_name, col_type, table_name)
                
                if "PRIMARY KEY" in pg_type:
                    # Handle as a separate constraint
                    column_def = f"{col_name} {pg_type.replace('PRIMARY KEY', '').strip()}"
                    primary_key = col_name
                else:
                    column_def = f"{col_name} {pg_type}"
                
                if not_null:
                    column_def += " NOT NULL"
                    
                if default_value:
                    # Clean up default value
                    if default_value.startswith("'") and default_value.endswith("'"):
                        default_value = default_value[1:-1]
                    column_def += f" DEFAULT {default_value}"
                    
                columns.append(column_def)
            
            # Add primary key constraint if needed
            if primary_key and "PRIMARY KEY" not in ''.join(columns):
                columns.append(f"PRIMARY KEY ({primary_key})")
            
            # Add foreign key constraints
            if table_name == 'timesheet_entries':
                columns.append("FOREIGN KEY (period_id) REFERENCES pay_periods(id)")
            
            # Create the table
            create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n  " + ",\n  ".join(columns) + "\n);"
            
            try:
                logger.info(f"Creating table {table_name}...")
                logger.debug(f"Executing SQL: {create_table_sql}")
                cursor.execute(create_table_sql)
            except psycopg2.Error as e:
                logger.error(f"Error creating table {table_name}: {e}")
                logger.error(f"SQL: {create_table_sql}")
                raise
        
        conn.commit()
        logger.info("All tables created successfully")

def migrate_data(tables):
    """Migrate data from SQLite to PostgreSQL"""
    with sqlite_connection() as sqlite_conn:
        sqlite_cursor = sqlite_conn.cursor()
        
        with postgres_connection() as pg_conn:
            pg_cursor = pg_conn.cursor()
            
            for table_name in tables:
                try:
                    # Get total count for progress reporting
                    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    total_rows = sqlite_cursor.fetchone()[0]
                    logger.info(f"Migrating {total_rows} rows from table {table_name}...")
                    
                    # Handle no data
                    if total_rows == 0:
                        logger.info(f"No data to migrate in table {table_name}")
                        continue
                    
                    # Get column names
                    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [col['name'] for col in sqlite_cursor.fetchall()]
                    
                    # Get data in batches
                    batch_size = 100
                    offset = 0
                    
                    while offset < total_rows:
                        # Make exceptions for timesheet_entries id column 
                        # which is auto-incremented in postgres as SERIAL
                        select_columns = columns
                        if table_name == 'timesheet_entries':
                            if 'id' in select_columns:
                                insert_columns = [col for col in columns if col != 'id']
                            else:
                                insert_columns = columns
                        else:
                            insert_columns = columns
                            
                        # Get data batch
                        sqlite_cursor.execute(
                            f"SELECT {', '.join(select_columns)} FROM {table_name} LIMIT {batch_size} OFFSET {offset}"
                        )
                        rows = sqlite_cursor.fetchall()
                        
                        if not rows:
                            break
                        
                        # Insert into PostgreSQL
                        for row in rows:
                            # For timesheet_entries, skip the id column
                            if table_name == 'timesheet_entries' and 'id' in columns:
                                values = [row[col] for col in row.keys() if col != 'id']
                            else:
                                values = [row[col] for col in row.keys()]
                            
                            placeholders = ', '.join(['%s'] * len(values))
                            
                            if table_name == 'timesheet_entries' and 'id' in columns:
                                cols_str = ', '.join([col for col in columns if col != 'id'])
                            else:
                                cols_str = ', '.join(columns)
                                
                            insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
                            
                            try:
                                pg_cursor.execute(insert_sql, values)
                            except psycopg2.Error as e:
                                logger.error(f"Error inserting into {table_name}: {e}")
                                logger.error(f"Data: {dict(row)}")
                                logger.error(f"SQL: {insert_sql}")
                                # Continue with next row instead of failing entire migration
                                continue
                        
                        pg_conn.commit()
                        offset += batch_size
                        logger.info(f"Migrated {min(offset, total_rows)}/{total_rows} rows from {table_name}")
                        
                    logger.info(f"Completed migration of table {table_name}")
                    
                    # Set sequence value for SERIAL columns
                    if table_name == 'timesheet_entries':
                        pg_cursor.execute("SELECT setval('timesheet_entries_id_seq', (SELECT MAX(id) FROM timesheet_entries))")
                        pg_conn.commit()
                
                except Exception as e:
                    logger.error(f"Error during migration of table {table_name}: {e}")
                    raise

def validate_migration(tables):
    """Validate that all data was migrated correctly"""
    with sqlite_connection() as sqlite_conn:
        sqlite_cursor = sqlite_conn.cursor()
        
        with postgres_connection() as pg_conn:
            pg_cursor = pg_conn.cursor()
            
            for table_name in tables:
                try:
                    # Count rows in SQLite
                    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    sqlite_count = sqlite_cursor.fetchone()[0]
                    
                    # Count rows in PostgreSQL
                    pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    pg_count = pg_cursor.fetchone()[0]
                    
                    if sqlite_count == pg_count:
                        logger.info(f"Validation successful for table {table_name}: {pg_count} rows")
                    else:
                        logger.warning(
                            f"Validation warning for table {table_name}: "
                            f"SQLite has {sqlite_count} rows, PostgreSQL has {pg_count} rows"
                        )
                except Exception as e:
                    logger.error(f"Error during validation of table {table_name}: {e}")
                    raise

def main():
    """Main migration function"""
    logger.info("Starting database migration from SQLite to PostgreSQL")
    logger.info(f"SQLite database: {SQLITE_DB_PATH}")
    logger.info(f"PostgreSQL database: {POSTGRES_URL.split('@')[1] if '@' in POSTGRES_URL else 'DATABASE_URL'}")
    
    try:
        # Get tables to migrate
        tables = get_sqlite_tables()
        logger.info(f"Found tables to migrate: {', '.join(tables)}")
        
        # Create tables in PostgreSQL
        create_postgres_tables(tables)
        
        # Migrate data
        migrate_data(tables)
        
        # Validate migration
        validate_migration(tables)
        
        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 