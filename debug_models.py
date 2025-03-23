import os
import sys

def list_model_files():
    """List all model files in the ccpayroll package"""
    print("Model files in ccpayroll:")
    for root, dirs, files in os.walk("ccpayroll"):
        for file in files:
            if file.endswith(".py"):
                print(f"- {os.path.join(root, file)}")

def read_model_file(filepath):
    """Read and print the content of a model file"""
    print(f"\nContents of {filepath}:")
    try:
        with open(filepath, "r") as f:
            print(f.read())
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    list_model_files()
    
    # Add specific files to check
    files_to_check = [
        "ccpayroll/models/employee.py",
        "ccpayroll/database/__init__.py",
        "app.py"
    ]
    
    for file in files_to_check:
        read_model_file(file) 