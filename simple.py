"""
Simple Flask app for testing deployment on Heroku
"""

from flask import Flask, render_template, jsonify
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'creative_closets_payroll_app')

@app.route('/')
def index():
    return jsonify({
        "status": "ok",
        "message": "CCPayroll app is running! (Temporary test version)"
    })

if __name__ == '__main__':
    app.run(debug=True) 