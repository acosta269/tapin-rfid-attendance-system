## Imports
import os
import json
import hashlib
from flask import Flask, jsonify, request, session
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

## Variables
# Create the Flask application.
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "tapin-development-secret-key")
app.permanent_session_lifetime = timedelta(hours=3)

# Store user records in the database folder.
USER_DATA_FILE = os.path.join(os.path.dirname(__file__), "database", "users.json")
# Open the shared dashboard after a successful login.
WEB_DASHBOARD = "/pages/dashboard.html"
# Assign separate UID ranges to each user role.
ROLE_UID_RANGES = {"admin": (1, 9), "hr": (10, 19), "employee": (20, float("inf"))}
# Remove devices that have not sent a heartbeat within this period.
DEVICE_TIMEOUT_SECONDS = 90

# Add CORS and no-cache headers to API responses.
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

# Track the latest status reported by each RFID device.
device_status = {}

# Store the latest employee record used by the application.
latest_employee = {
    "uid": None,
    "rfid": None,
    "employeeid": None,
    "lastname": None,
    "firstname": None,
    "address": None,
    "bdate": None,
    "cpnumber": None,
    "email": None,
    "username": None,
    "password_hash": None,
    "role": None,
    "image": None,
    "timestamp_creation": None,
    "timestamp_modified": None
}

# Store the latest RFID scan received from a device.
latest_scan = {
    "rfid": None,
    "scanned_at": None
}

## Functions
# Build the RFID lookup database from all user roles.
def load_employee_database():
    if not os.path.exists(USER_DATA_FILE):
        print("File not found: database/users.json - database is empty")
        return {}
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("Error reading database/users.json:", str(e))
        return {}

    db = {}
    for category in ["admin", "hr", "employees"]:
        if category in data:
            for emp in data[category]:
                rfid = emp.get("rfid", "").strip().upper()
                if rfid:
                    emp["role"] = "employee" if category == "employees" else category
                    db[rfid] = emp
        print("Loaded", len(db), "employees from database/users.json")
    return db

employee_database = load_employee_database()

# Delete devices that have stopped sending heartbeat pings.
def remove_offline_devices():
    current_time = datetime.now()
    offline_devices = [
        device_id for device_id, data in device_status.items()
        if (current_time - data["last_seen_at"]).total_seconds() > DEVICE_TIMEOUT_SECONDS
    ]
    for device_id in offline_devices:
        del device_status[device_id]

# Get the current online device list for web display.
def get_online_devices():
    remove_offline_devices()
    return [
        {
            "device_id": device_id,
            "status": data["status"],
            "last_seen": data["last_seen"],
        }
        for device_id, data in device_status.items()
    ]

## Routes
# Register a new admin, HR, or employee account.
@app.route("/api/register-employee", methods=["POST"])
def register_employee():
    try:
        data = request.form
        required = ["employeeid", "rfid", "lastname", "firstname", "address", "bdate", "cpnumber", "email", "username", "password", "role"]
        if not data or not all(key in data for key in required):
            return jsonify({
                "status": "error",
                "message": "Missing required fields",
                "required_fields": required
            }), 400
        
        # Store the account in the database section selected by its role.
        role = str(data.get("role", "employee")).strip().lower()
        if role not in ["admin", "hr", "employee"]:
            return jsonify({
                "status": "error",
                "message": "Role must be admin, hr, or employee"
            }), 400

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        category = "employees" if role == "employee" else role
        image_file = request.files.get("image")
        image_path = ""
        if image_file and image_file.filename:
            extension = os.path.splitext(image_file.filename)[1].lower()
            if extension not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                return jsonify({
                    "status": "error",
                    "message": "Image must be JPG, JPEG, PNG, GIF, or WEBP"
                }), 400

        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            database = json.load(f)

        username = str(data.get("username", "")).strip()
        rfid = str(data.get("rfid", "")).strip().upper()
        if any(emp.get("rfid", "").strip().upper() == rfid or emp.get("username") == username
               for records in database.values() for emp in records):
            return jsonify({
                "status": "error",
                "message": "RFID or username is already registered"
            }), 409

        uid_start, uid_end = ROLE_UID_RANGES[role]
        employee_uids = [
            int(emp.get("uid"))
            for records in database.values()
            for emp in records
            if str(emp.get("uid", "")).isdigit()
        ]
        role_uids = [value for value in employee_uids if uid_start <= value <= uid_end]
        uid = str(max([uid_start - 1] + role_uids) + 1).zfill(3)

        if image_file and image_file.filename:
            employee_id_filename = secure_filename(str(data.get("employeeid", "")))
            image_directory = os.path.join(os.path.dirname(__file__), "storage", "profiles", category, uid)
            os.makedirs(image_directory, exist_ok=True)
            image_file.save(os.path.join(image_directory, employee_id_filename + extension))
            image_path = os.path.join("storage", "profiles", category, uid, employee_id_filename + extension).replace(os.sep, "/")

        employee = {
            "uid": uid,
            "rfid": rfid,
            "employeeid": str(data.get("employeeid", "")).strip(),
            "lastname": str(data.get("lastname", "")).strip(),
            "firstname": str(data.get("firstname", "")).strip(),
            "address": str(data.get("address", "")).strip(),
            "bdate": str(data.get("bdate", "")).strip(),
            "cpnumber": str(data.get("cpnumber", "")).strip(),
            "email": str(data.get("email", "")).strip(),
            "username": str(data.get("username", "")).strip(),
            "password_hash": hashlib.md5(str(data.get("password", "")).encode("utf-8")).hexdigest(),
            "role": role,
            "image": image_path,
            "timestamp_creation": now,
            "timestamp_modified": now
        }
        database.setdefault(category, []).append(employee)
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(database, f, indent=4)
            f.write("\n")

        employee_database[rfid] = employee

        print("Registered:", employee["firstname"], employee["lastname"], "UID:", uid, "RFID:", rfid)
        return jsonify({
            "status": "success",
            "message": "Employee registered successfully",
            "data": employee
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Registration failed: " + str(e)
        }), 500

# Authenticate all roles and create a three-hour session.
@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "Username and password are required"
            }), 400

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()
        password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()

        for emp in employee_database.values():
            if emp.get("username") == username:
                if password_hash == emp.get("password_hash", "").lower():
                    # Admin and HR use the command center; employees use the main dashboard.
                    role = emp.get("role", "employee")
                    session.permanent = True
                    session["user"] = {
                        "uid": emp.get("uid"),
                        "employeeid": emp.get("employeeid"),
                        "username": emp.get("username"),
                        "fullname": emp.get("firstname", "") + " " + emp.get("lastname", ""),
                        "role": role,
                        "rfid": emp.get("rfid")
                    }
                    return jsonify({
                        "status": "success",
                        "message": "Login successful",
                        "redirect": WEB_DASHBOARD + ("#admin-dashboard" if role in ["admin", "hr"] else "#dashboard"),
                        "user": {
                            "uid": emp.get("uid"),
                            "employeeid": emp.get("employeeid"),
                            "username": emp.get("username"),
                            "fullname": emp.get("firstname", "") + " " + emp.get("lastname", ""),
                            "role": role,
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

# Return the currently authenticated user's session.
@app.route("/api/session", methods=["GET"])
def get_session():
    user = session.get("user")
    if not user:
        return jsonify({
            "status": "error",
            "message": "Session expired or user is not logged in"
        }), 401
    return jsonify({
        "status": "success",
        "user": user
    }), 200

# Clear the authenticated user's session.
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({
        "status": "success",
        "message": "Logged out successfully"
    }), 200

# Semi Web Routes
# Return the latest RFID scan and online devices for the web dashboard.
@app.route("/api/get-latest-rfid", methods=["GET"])
def get_latest_rfid():
    rfid = latest_scan.get("rfid")
    scanned_at = latest_scan.get("scanned_at")
    employee = employee_database.get(rfid) if rfid else None

    return jsonify({
        "status": "success",
        "rfid": rfid,
        "scanned_at": scanned_at,
        "devices": get_online_devices(),
        "found": bool(employee),
        "employee": {
            "employeeid": employee.get("employeeid"),
            "lastname": employee.get("lastname"),
            "firstname": employee.get("firstname"),
            "image": employee.get("image")
        } if employee else None
    }), 200

# Web display route for current device heartbeats.
# Return devices that have sent a recent ping.
@app.route("/api/get-device-status", methods=["GET"])
def get_device_status():
    return jsonify({
        "status": "success",
        "devices": get_online_devices()
    }), 200

# API routes
# Check whether one device is currently online.
@app.route("/api/check-device/<device_id>", methods=["GET"])
def check_device(device_id):
    remove_offline_devices()
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

# Reload users.json into the in-memory RFID lookup database.
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
# Receive a heartbeat ping from an RFID device.
@app.route("/api/device-ping", methods=["POST"])
def device_ping():
    try:
        data = request.get_json()
        if not data or not data.get("device_id"):
            return jsonify({
                "status": "error",
                "message": "Missing required field: device_id"
            }), 400
        device_id = str(data["device_id"]).strip()
        status = data.get("status", "alive")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        device_status[device_id] = {
            "status": status,
            "last_seen": now,
            "last_seen_at": datetime.now()
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

# Receive an RFID scan and match it to a user record.
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
# Return a consistent JSON response for unknown routes.
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