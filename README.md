# Creative Closets Payroll System

A web-based payroll management system designed to mimic the functionality of the Excel-based payroll system used by Creative Closets.

## Features

- **Employee Management**: Add, edit, and delete employees with hourly rates
- **Pay Period Management**: Create weekly pay periods for tracking employee work
- **Timesheet Entry**: Enter hours worked and pay for each employee by day
- **Automatic Pay Calculation**: Automatically calculate pay based on hours worked and hourly rate
- **Reporting**: Generate comprehensive payroll reports with visualizations
- **Import/Export**: Import data from Excel files and export timesheets to Excel

## Installation

1. Clone the repository:
```
git clone https://github.com/yourusername/creative-closets-payroll.git
cd creative-closets-payroll
```

2. Create a virtual environment and activate it:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```
pip install -r requirements.txt
```

4. Run the application:
```
python app.py
```

5. Open your browser and navigate to `http://localhost:5000`

## Usage

### Managing Employees

1. Navigate to the "Employees" section
2. Add new employees with their names and hourly rates
3. Edit or delete existing employees as needed

### Managing Pay Periods

1. Navigate to the "Pay Periods" section
2. Create a new pay period by specifying start and end dates
3. The system will automatically create a timesheet for the period

### Entering Timesheet Data

1. Navigate to the "Pay Periods" section
2. Click "Edit Timesheet" for the desired pay period
3. Enter hours worked or pay directly for each employee and day
4. Data is saved automatically as you enter it

### Generating Reports

1. Navigate to the "Reports" section
2. Select a pay period or choose "All Pay Periods"
3. Click "Generate Report" to view payroll data and visualizations

### Importing/Exporting Data

1. Navigate to the "Import/Export" section
2. To import data, select an Excel file and click "Import Data"
3. To export data, select a pay period and click "Export Data"

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Database System

The application now uses SQLite for data storage, which provides the following benefits:

1. **Data Integrity**: Prevents data corruption issues that were occurring with JSON files
2. **Transactional Support**: Each update is atomic, preventing partial writes
3. **Concurrency**: Properly handles multiple simultaneous updates
4. **Better Performance**: More efficient for larger datasets

### Migration Process

When you first run the application after this update, it will automatically:

1. Initialize the SQLite database (stored in `data/payroll.db`)
2. Migrate all existing data from JSON files to the database
3. Keep the original JSON files as backup

No manual migration steps are required. Your existing data will be preserved.

### Troubleshooting

If you experience any issues after migration:

1. Check the `data/payroll.log` file for error messages
2. Use the `/fix-timesheet/<period_id>` route to reset a specific timesheet if needed 