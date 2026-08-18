## Imports
import os
import json
from flask import Flask, jsonify, request
from datetime import datetime

## Variables
app = Flask(__name__)

USER_DATA_FILE = "user.json"

device_status = {}

latest_employee = {
    "uid": None,
    "employeeid": None,
    "rfid": None,
    "lastname": None,
    "firstname": None,
    "address": None,
    "bdate": None,
    "cpnumber": None,
    "email": None,
    "image": None,
    "timestamp_modified": None,
    "timestamp_creation": None
}

latest_scan = {
    "rfid": None,
    "scanned_at": None
}

## Functions
# Load database from JSON file
def load_employee_database():
    if not os.path.exists(USER_DATA_FILE):
        print("File not found: user.json - database is empty")
        return {}
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("Error reading user.json:", str(e))
        return {}

    db = {}
    for category in ["admin", "hr", "employees"]:
        if category in data:
            for emp in data[category]:
                rfid = emp.get("rfid", "").strip().upper()
                if rfid:
                    db[rfid] = emp
    print("Loaded", len(db), "employees from user.json")
    return db

employee_database = load_employee_database()

## Routes
# Web Routes
@app.route("/api/register-employee", methods=["POST"])
def register_employee():
    try:
        from werkzeug.security import generate_password_hash
        data = request.get_json()
        required = ["employeeid", "rfid", "lastname", "firstname", "address", "bdate", "cpnumber", "email", "username", "password"]
        if not data or not all(key in data for key in required):
            return jsonify({
                "status": "error",
                "message": "Missing required fields",
                "required_fields": required
            }), 400
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rfid = str(data.get("rfid", "")).strip().upper()

        employee_database[rfid] = {
            "uid": data.get("employeeid"),
            "employeeid": str(data.get("employeeid", "")).strip(),
            "rfid": rfid,
            "lastname": str(data.get("lastname", "")).strip(),
            "firstname": str(data.get("firstname", "")).strip(),
            "address": str(data.get("address", "")).strip(),
            "bdate": str(data.get("bdate", "")).strip(),
            "cpnumber": str(data.get("cpnumber", "")).strip(),
            "email": str(data.get("email", "")).strip(),
            "username": str(data.get("username", "")).strip(),
            "password_hash": generate_password_hash(str(data.get("password", ""))),
            "image": data.get("image", ""),
            "timestamp_creation": now,
            "timestamp_modified": now
        }

        print("Registered:", employee_database[rfid]["firstname"], employee_database[rfid]["lastname"], "RFID:", rfid)
        return jsonify({
            "status": "success",
            "message": "Employee registered successfully",
            "data": employee_database[rfid]
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Registration failed: " + str(e)
        }), 500

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()

        for rfid, emp in employee_database.items():
            if emp.get("username") == username:
                if password == emp.get("password_hash", ""):
                    return jsonify({
                        "status": "success",
                        "message": "Login successful",
                        "user": {
                            "employeeid": emp.get("employeeid"),
                            "username": emp.get("username"),
                            "fullname": emp.get("firstname", "") + " " + emp.get("lastname", ""),
                            "role": emp.get("role", "employee"),
                            "rfid": emp.get("rfid")
                        }
                    }), 200

        return jsonify({
            "status": "error",
            "message": "Invalid username or password"
        }), 401
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Semi Web Routes
@app.route("/api/get-latest-rfid", methods=["GET"])
def get_latest_rfid():
    rfid = latest_scan.get("rfid")
    scanned_at = latest_scan.get("scanned_at")
    employee = employee_database.get(rfid) if rfid else None

    return jsonify({
        "status": "success",
        "rfid": rfid,
        "scanned_at": scanned_at,
        "found": bool(employee),
        "employee": {
            "employeeid": employee.get("employeeid"),
            "lastname": employee.get("lastname"),
            "firstname": employee.get("firstname"),
            "image": employee.get("image")
        } if employee else None
    }), 200

# API routes
@app.route("/api/check-device/<device_id>", methods=["GET"])
def check_device(device_id):
    data = device_status.get(device_id)
    if not data:
        return jsonify({
            "status": "unknown",
            "message": "Device not found"
        }), 404
    return jsonify({
        "status": "success",
        "device_id": device_id,
        "device_status": data["status"],
        "last_seen": data["last_seen"]
    }), 200

@app.route("/api/reload-db", methods=["POST"])
def reload_db():
    global employee_database
    employee_database = load_employee_database()
    return jsonify({
        "status": "success",
        "message": "Database reloaded",
        "total": len(employee_database)
    }), 200

# IoT Routes
@app.route("/api/device-ping", methods=["POST"])
def device_ping():
    try:
        data = request.get_json()
        device_id = data.get("device_id", "unknown")
        status = data.get("status", "alive")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        device_status[device_id] = {
            "status": status,
            "last_seen": now
        }
        print("Ping received from", device_id, "Last seen:", now)
        return jsonify({
            "status": "success",
            "message": "Ping recorded",
            "device_id": device_id,
            "last_seen": now
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/api/receive-rfid", methods=["POST"])
def receive_rfid():
    try:
        data = request.get_json()
        if not data or "rfid" not in data or "scanned_at" not in data:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: rfid and scanned_at"
            }), 400

        rfid = str(data["rfid"]).strip().upper()
        scanned_at = str(data["scanned_at"])

        latest_scan["rfid"] = rfid
        latest_scan["scanned_at"] = scanned_at

        employee = employee_database.get(rfid)

        print("RFID Received:", rfid, "at", scanned_at)

        if employee:
            print("RFID Matched:", employee["firstname"], employee["lastname"], "ID:", employee["employeeid"])
            return jsonify({
                "status": "success",
                "message": "RFID received and matched",
                "found": True
            }), 200
        else:
            print("No match for RFID:", rfid)
            return jsonify({
                "status": "success",
                "message": "RFID received - Not registered",
                "found": False
            }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Server error: " + str(e)
        }), 500

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return jsonify({
        "status": "error",
        "message": "Invalid request",
        "timestamp": datetime.now().isoformat()
    }), 404

## Main
if __name__ == "__main__":
    app.run()
    #app.run(debug=True, port=5001)