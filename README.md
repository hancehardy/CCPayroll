# Creative Closets Payroll

A payroll management application for Creative Closets, designed to handle employee data, pay periods, timesheet entries, and generate payroll reports.

## Features

- Employee management (add, edit, delete)
- Pay period management
- Timesheet entry and tracking
- Payroll reports (PDF and CSV formats)
- Support for different pay types (hourly, salary, commission, salary+hourly)

## Requirements

- Python 3.8+
- Flask
- PostgreSQL
- wkhtmltopdf (for PDF generation)
- Other dependencies listed in requirements.txt

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/CCPayroll.git
   cd CCPayroll
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install wkhtmltopdf (system dependency for PDF generation):
   - On Ubuntu/Debian: `sudo apt-get install wkhtmltopdf`
   - On macOS: `brew install wkhtmltopdf`
   - On Windows: Download and install from https://wkhtmltopdf.org/downloads.html

## Usage

1. Run the application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Project Structure

- `ccpayroll/` - Main application package
  - `__init__.py` - Application factory
  - `database/` - Database management
  - `models/` - Data models
  - `routes/` - Route blueprints
  - `static/` - Static assets (CSS, JS, images)
  - `templates/` - Jinja2 templates
  - `utils/` - Utility functions
  - `reports/` - Report generation

## Development

To run the application in development mode:

```bash
python app.py
```

## Testing

To run tests:

```bash
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Directory Structure

- `app.py`: Main application file
- `templates/`: HTML templates for the web interface
- `static/`: Static files (CSS, JavaScript, images)
- `data/`: JSON files for storing application data
- `uploads/`: Temporary storage for uploaded and exported files
- `requirements.txt`: List of required Python packages

## Technologies Used

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Data Processing**: Pandas, NumPy
- **Visualization**: Matplotlib
- **Data Storage**: JSON files

## Database

The application now uses PostgreSQL for data storage, which provides the following benefits:

1. Better performance and scalability for larger payroll datasets
2. Advanced data integrity and relational capabilities
3. Enterprise-grade database technology
4. Concurrent access support
5. Better backup and recovery options

To set up the database:

1. Install PostgreSQL if not already installed
2. Create a PostgreSQL database:
   ```
   createdb ccpayroll
   ```
3. Update the `.env` file with your PostgreSQL credentials:
   ```
   PG_HOST=localhost
   PG_PORT=5432
   PG_USER=your_username
   PG_PASSWORD=your_password
   PG_DB=ccpayroll
   ```
4. The application will initialize the database tables automatically on first run

Previously, the application used SQLite. If you're upgrading from a previous version, see the "Database Migration from SQLite to PostgreSQL" section below.

### Migration Process

When you first run the application after this update, it will automatically:

1. Initialize the PostgreSQL database tables
2. Migrate any existing data from JSON files directly to PostgreSQL
3. Keep the original JSON files as backup

No manual migration steps are required if you are coming from the JSON-based version. Your existing data will be preserved.

### Troubleshooting

If you experience any issues after migration:

1. Check the `data/payroll.log` file for error messages
2. Use the `/fix-timesheet/<period_id>` route to reset a specific timesheet if needed

## Database Migration from SQLite to PostgreSQL

This application has been updated to use PostgreSQL instead of SQLite. To migrate your existing data:

1. Install PostgreSQL if not already installed
2. Create a PostgreSQL database:
   ```
   createdb ccpayroll
   ```
3. Update the `.env` file with your PostgreSQL credentials:
   ```
   PG_HOST=localhost
   PG_PORT=5432
   PG_USER=your_username
   PG_PASSWORD=your_password
   PG_DB=ccpayroll
   ```
4. Run the migration script to transfer data from SQLite to PostgreSQL:
   ```
   python migrate_db.py
   ```
5. Run the application normally:
   ```
   python app.py
   ```

The migration script will:
1. Extract all data from your existing SQLite database
2. Create the necessary tables in PostgreSQL
3. Insert the data into PostgreSQL

After successful migration, the SQLite database file will be automatically removed. 