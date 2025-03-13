import pandas as pd
import os

# Path to the Excel file
excel_file = os.path.join('Local Docs', 'PAYROLL 2025.xlsx')

# Read the Excel file
print(f"Reading Excel file: {excel_file}")
try:
    # First, get the sheet names
    xl = pd.ExcelFile(excel_file)
    sheet_names = xl.sheet_names
    print(f"Sheet names: {sheet_names}")
    
    # Read each sheet and display basic information
    for sheet in sheet_names:
        print(f"\nAnalyzing sheet: {sheet}")
        df = pd.read_excel(excel_file, sheet_name=sheet)
        
        # Display basic information
        print(f"Shape: {df.shape}")
        print("Column names:")
        for col in df.columns:
            print(f"  - {col}")
        
        # Display first few rows to understand the data
        print("\nFirst 5 rows:")
        print(df.head())
        
        # Check for numeric columns that could be used for index calculation
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            print("\nNumeric columns that could be used for index calculation:")
            for col in numeric_cols:
                print(f"  - {col}")
    
    print("\nTo compute an index, we need to know which specific calculation you want to perform.")
    print("For example, do you want to:")
    print("1. Calculate a weighted average of certain columns?")
    print("2. Create a composite index based on multiple metrics?")
    print("3. Normalize and aggregate specific data points?")
    print("4. Something else?")
    
except Exception as e:
    print(f"Error reading Excel file: {e}") 