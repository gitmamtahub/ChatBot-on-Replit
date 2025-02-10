# pip install fuzzywuzzy python-Levenshtein nltk flask

import sqlite3
import nltk
import logging
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from fuzzywuzzy import process

nltk.download('punkt_tab')

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_db_connection():
    conn = sqlite3.connect("employees.db", check_same_thread=False)
    return conn

def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Employees table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Employees (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Department TEXT NOT NULL,
        Salary REAL NOT NULL,
        Hire_Date TEXT NOT NULL
    )
    ''')

    # Create Departments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Departments (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL UNIQUE,
        Manager TEXT NOT NULL
    )
    ''')

    # Insert sample data
    cursor.executemany('''
    INSERT INTO Employees (Name, Department, Salary, Hire_Date) VALUES (?, ?, ?, ?)
    ''', [
        ('Alice Johnson', 'HR', 60000, '2020-05-10'),
        ('Bob Smith', 'IT', 80000, '2019-08-21'),
        ('Charlie Lee', 'Finance', 75000, '2021-03-15'),
        ('Diana Prince', 'HR', 65000, '2018-07-01'),
        ('Eve Williams', 'IT', 90000, '2020-12-05'),
        ('Frank Gracia', 'Finance', 70000, '2021-06-30'),
        ('Grace Brown', 'HR', 68000, '2019-09-28')       
    ])

    cursor.executemany('''
    INSERT OR IGNORE INTO Departments (Name, Manager) VALUES (?, ?)
    ''', [
        ('HR', 'Eve Adams'),
        ('IT', 'John Doe'),
        ('Finance', 'Mary Johnson')
    ])

    conn.commit()
    conn.close()
    logging.info("Database setup complete.")

@app.route("/")
def home():
    return send_from_directory("", "index.html")  # Serve frontend


# ✅ Define User Queries & Corresponding SQL Commands
QUERY_DB = {
    "show all employees in [DEPT]": "SELECT DISTINCT Name FROM Employees WHERE LOWER(Department) = LOWER(?)",
    "who is the manager of [DEPT]": "SELECT Manager FROM Departments WHERE LOWER(Name) = LOWER(?)",
    "list employees hired after [DATE]": "SELECT Name FROM Employees WHERE Hire_Date > ?",
    "total salary expense for [DEPT]": "SELECT SUM(Salary) FROM Employees WHERE LOWER(Department) = LOWER(?)"
}

@app.route("/query", methods=["GET"])
def process_natural_query():
    """Process user query using fuzzy matching"""
    user_query = request.args.get("query", "").strip().lower()

    if not user_query:
        return jsonify({"error": "Query cannot be empty"}), 400

    # Find best match using fuzzy matching
    best_match, similarity = process.extractOne(user_query, QUERY_DB.keys())

    # If similarity is too low, return error
    if similarity < 40:  # Adjust the threshold if needed
        return jsonify({"error": "Query not understood. Try rephrasing."}), 400

    sql_query = QUERY_DB[best_match]

    # ✅ Extract department name if query is related to departments
    if "[DEPT]" in best_match:
        dept_match = re.search(r"in (\w+) department", user_query)
        if dept_match:
            entity = dept_match.group(1)  # Extract department name
        else:
            words = nltk.word_tokenize(user_query)
            entity = words[-1]  # Fallback to last word if regex fails

    # ✅ Extract date if query is related to hiring date
    elif "[DATE]" in best_match:
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", user_query)
        if date_match:
            entity = date_match.group(1)  # Extract the date
        else:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    else:
        return jsonify({"error": "Query type not recognized."}), 400


    # Query SQLite Database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql_query, (entity,))
    result = cursor.fetchall()
    conn.close()

    # ✅ Return formatted response
    return jsonify({
        "query": user_query,
        "matched_template": best_match,
        "similarity_score": similarity,
        "result": [row[0] for row in result]  # Extract data from tuples
    })

if __name__ == "__main__":
    setup_database()
    app.run(host="0.0.0.0", port=8080, debug=True)
