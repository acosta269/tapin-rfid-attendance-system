## Imports
import os
import json
import hashlib
import calendar
from flask import Flask, jsonify, request, session
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

## Variables
# Create the Flask application.
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "tapin-development-secret-key")
app.permanent_session_lifetime = timedelta(hours=3)

# Update session cookie settings for better compatibility
app.config.update(
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_PATH='/',
    SESSION_COOKIE_DOMAIN=None
)

# Store user records in the database folder.
USER_DATA_FILE = os.path.join(os.path.dirname(__file__), "database", "users.json")
# Store every received RFID scan and timestamp.
ATTENDANCE_DATA_FILE = os.path.join(os.path.dirname(__file__), "database", "attendance.json")
# Open the shared dashboard after a successful login.
WEB_DASHBOARD = "/pages/dashboard.html"
EMPLOYEE_DASHBOARD = "/pages/employee-dashboard.html"
# Choose the frontend destination from the role stored in users.json.
ROLE_DASHBOARDS = {
    "admin": WEB_DASHBOARD,
    "hr": WEB_DASHBOARD,
    "employee": EMPLOYEE_DASHBOARD,
}
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
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Cookie, Set-Cookie"
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
# Load persisted DTR records and scan events.
def load_attendance_data():
    if not os.path.exists(ATTENDANCE_DATA_FILE):
        return {"records": [], "scan_events": []}
    try:
        with open(ATTENDANCE_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return {"records": [], "scan_events": data}
            if "dtr" in data:
                working_days = list(data.get("dtr", {}).values())
                template_record = {
                    "id": data.get("id") or "001",
                    "uid": data.get("uid", ""),
                    "employeeid": data.get("employeeid", ""),
                    "rfid": data.get("rfid", ""),
                    "fullname": f"{data.get('firstname', '')} {data.get('lastname', '')}".strip(),
                    "position": data.get("position"),
                    "department": data.get("department"),
                    "month": "2026-09",
                    "working_days": working_days,
                    "total_hours": "0.00",
                    "total_ut": "0.00",
                    "total_ot": "0.00"
                }
                return {
                    "records": [template_record] if template_record["uid"] else [],
                    "scan_events": []
                }
            return {
                "records": data.get("records", []),
                "scan_events": data.get("scan_events", [])
            }
    except (OSError, ValueError):
        return {"records": [], "scan_events": []}

attendance_data = load_attendance_data()
attendance_records = attendance_data["records"]
scan_events = attendance_data["scan_events"]
if scan_events:
    latest_scan.update({
        "rfid": scan_events[-1].get("rfid"),
        "scanned_at": scan_events[-1].get("scanned_at")
    })

## Functions
# Save DTR records and scan history to the attendance database.
def save_attendance_data():
    with open(ATTENDANCE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "records": attendance_records,
            "scan_events": scan_events[-10000:]
        }, f, indent=4)
        f.write("\n")

# Build calendar rows for one DTR month.
def build_working_days(year, month):
    return [
        {
            "date": f"{year:04d}-{month:02d}-{day:02d}",
            "day": calendar.day_abbr[calendar.weekday(year, month, day)],
            "am_in": "",
            "am_out": "",
            "pm_in": "",
            "pm_out": "",
            "hours": "0.00",
            "ut": "0.00",
            "ot": "0.00"
        }
        for day in range(1, calendar.monthrange(year, month)[1] + 1)
    ]

# Find or create a DTR record using the user's identity fields.
def get_attendance_record(employee, scan_date):
    existing_ids = [int(r.get("id", 0)) for r in attendance_records if str(r.get("id", "")).isdigit()]
    new_id = str(max(existing_ids + [0]) + 1).zfill(3)
    
    for record in attendance_records:
        if record.get("uid") == employee.get("uid") and record.get("month") == month_key:
            return record

    month_key = scan_date.strftime("%Y-%m")

    record = {
        "id": new_id,
        "uid": employee.get("uid"),
        "employeeid": employee.get("employeeid"),
        "rfid": employee.get("rfid"),
        "fullname": f"{employee.get('firstname', '')} {employee.get('lastname', '')}".strip(),
        "position": employee.get("position"),
        "department": employee.get("department"),
        "month": month_key,
        "working_days": build_working_days(scan_date.year, scan_date.month),
        "total_hours": "0.00",
        "total_ut": "0.00",
        "total_ot": "0.00"
    }
    attendance_records.append(record)
    return record

# Add a device timestamp to the correct AM or PM DTR slot.
def record_attendance_scan(employee, scanned_at):
    scan_time = parse_scan_time(scanned_at)

    record = get_attendance_record(employee, scan_time)
    day_record = next(day for day in record["working_days"] if day["date"] == scan_time.strftime("%Y-%m-%d"))
    time_value = scan_time.strftime("%H:%M:%S")
    period = "am" if scan_time.hour < 12 else "pm"
    in_key = f"{period}_in"
    out_key = f"{period}_out"
    if not day_record[in_key]:
        day_record[in_key] = time_value
    elif not day_record[out_key]:
        day_record[out_key] = time_value

    am_hours = calculate_hours(day_record["am_in"], day_record["am_out"])
    pm_hours = calculate_hours(day_record["pm_in"], day_record["pm_out"])
    total_hours = am_hours + pm_hours
    day_record["hours"] = f"{total_hours:.2f}"
    day_record["ut"] = f"{max(0, 8 - total_hours):.2f}"
    day_record["ot"] = f"{max(0, total_hours - 8):.2f}"
    record["total_hours"] = f"{sum(float(day['hours']) for day in record['working_days']):.2f}"
    record["total_ut"] = f"{sum(float(day['ut']) for day in record['working_days']):.2f}"
    record["total_ot"] = f"{sum(float(day['ot']) for day in record['working_days']):.2f}"
    return record

# Parse the timestamp supplied by the RFID device.
def parse_scan_time(scanned_at):
    try:
        return datetime.strptime(scanned_at, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return datetime.now()

# Calculate completed hours between an in and out time.
def calculate_hours(start_time, end_time):
    if not start_time or not end_time:
        return 0
    start = datetime.strptime(start_time, "%H:%M:%S")
    end = datetime.strptime(end_time, "%H:%M:%S")
    return max(0, (end - start).total_seconds() / 3600)

# Ensure every registered user has a DTR record for the current month.
def initialize_attendance_records():
    current_month = datetime.now()
    for employee in employee_database.values():
        get_attendance_record(employee, current_month)
    save_attendance_data()

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

# Calculate live attendance totals from today's recognized RFID scans.
def get_dashboard_statistics():
    today = datetime.now().date()
    today_events = [event for event in scan_events if event["scanned_on"] == today.isoformat()]
    employee_rfids = {
        emp.get("rfid", "").strip().upper()
        for emp in employee_database.values()
        if emp.get("role") == "employee"
    }
    present_rfids = {
        event["rfid"] for event in today_events
        if event["rfid"] in employee_rfids
    }
    total_employees = len(employee_rfids)
    present_today = len(present_rfids)
    absent_today = max(total_employees - present_today, 0)
    attendance_rate = round((present_today / total_employees) * 100, 1) if total_employees else 0

    return {
        "total_employees": total_employees,
        "present_today": present_today,
        "absent_today": absent_today,
        "employees_late": 0,
        "on_leave": 0,
        "attendance_rate": attendance_rate,
        "rfid_scans_today": len(today_events),
        "departments": 0,
    }

# Prepare recent scans and user records for the dashboard UI.
def get_dashboard_data():
    recent_scans = []
    for event in reversed(scan_events[-50:]):
        employee = employee_database.get(event["rfid"])
        recent_scans.append({
            "rfid": event["rfid"],
            "scanned_at": event["scanned_at"],
            "found": bool(employee),
            "employee": {
                "uid": employee.get("uid"),
                "employeeid": employee.get("employeeid"),
                "lastname": employee.get("lastname"),
                "firstname": employee.get("firstname"),
                "role": employee.get("role"),
                "department": employee.get("department"),
                "image": employee.get("image")
            } if employee else None
        })

    users = [
        {
            "uid": employee.get("uid"),
            "rfid": employee.get("rfid"),
            "employeeid": employee.get("employeeid"),
            "lastname": employee.get("lastname"),
            "firstname": employee.get("firstname"),
            "address": employee.get("address"),
            "bdate": employee.get("bdate"),
            "cpnumber": employee.get("cpnumber"),
            "email": employee.get("email"),
            "username": employee.get("username"),
            "role": employee.get("role"),
            "department": employee.get("department"),
            "position": employee.get("position"),
            "image": employee.get("image"),
            "timestamp_creation": employee.get("timestamp_creation"),
            "timestamp_modified": employee.get("timestamp_modified")
        }
        for employee in employee_database.values()
    ]
    return {
        "stats": get_dashboard_statistics(),
        "users": users,
        "attendance": attendance_records,
        "scans": recent_scans,
        "devices": get_online_devices(),
        "latest_scan": recent_scans[0] if recent_scans else None
    }

# Return only the supported role from a user record.
def get_user_role(user):
    role = str(user.get("role", "employee")).strip().lower()
    return role if role in ROLE_DASHBOARDS else "employee"

# Build the frontend destination for the authenticated role.
def get_role_redirect(role):
    return ROLE_DASHBOARDS[role]

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
            "department": None,
            "position": None,
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
                    role = get_user_role(emp)
                    session.permanent = True
                    session["user"] = {
                        "uid": emp.get("uid"),
                        "employeeid": emp.get("employeeid"),
                        "username": emp.get("username"),
                        "fullname": emp.get("firstname", "") + " " + emp.get("lastname", ""),
                        "role": role,
                        "rfid": emp.get("rfid")
                    }
                    # Mark session as modified to ensure it's saved
                    session.modified = True
                    return jsonify({
                        "status": "success",
                        "message": "Login successful",
                        "redirect": get_role_redirect(role),
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
            "uid": employee.get("uid"),
            "rfid": employee.get("rfid"),
            "employeeid": employee.get("employeeid"),
            "lastname": employee.get("lastname"),
            "firstname": employee.get("firstname"),
            "role": employee.get("role"),
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

# Return live employee and RFID totals for the dashboard cards.
@app.route("/api/dashboard-stats", methods=["GET"])
def dashboard_stats():
    return jsonify({
        "status": "success",
        "stats": get_dashboard_statistics()
    }), 200

# Return all current dashboard data in one authenticated response.
@app.route("/api/dashboard-data", methods=["GET"])
def dashboard_data():
    if not session.get("user"):
        return jsonify({
            "status": "error",
            "message": "Session expired or user is not logged in"
        }), 401
    return jsonify({
        "status": "success",
        "data": get_dashboard_data()
    }), 200

# Return persistent DTR records for a requested month.
@app.route("/api/attendance", methods=["GET"])
def get_attendance():
    if not session.get("user"):
        return jsonify({
            "status": "error",
            "message": "Session expired or user is not logged in"
        }), 401
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    records = [record for record in attendance_records if record.get("month") == month]
    return jsonify({
        "status": "success",
        "month": month,
        "records": records
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
    initialize_attendance_records()
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
        scan_event = {
            "rfid": rfid,
            "scanned_at": scanned_at,
            "scanned_on": datetime.now().date().isoformat()
        }
        scan_events.append(scan_event)

        employee = employee_database.get(rfid)
        if employee:
            record_attendance_scan(employee, scanned_at)
        else:
            print("RFID not found in database:", rfid)

        save_attendance_data()

        print("RFID Received:", rfid, "at", scanned_at)

        if employee:
            print("RFID Matched:", employee["firstname"], employee["lastname"], "ID:", employee["employeeid"])
            return jsonify({
                "status": "success",
                "message": "RFID received and matched",
                "rfid": rfid,
                "scanned_at": scanned_at,
                "found": True
            }), 200
        else:
            print("No match for RFID:", rfid)
            return jsonify({
                "status": "success",
                "message": "RFID received - Not registered",
                "rfid": rfid,
                "scanned_at": scanned_at,
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

# OPTIONS handlers for CORS preflight
@app.route("/api/login", methods=["OPTIONS"])
@app.route("/api/session", methods=["OPTIONS"])
@app.route("/api/logout", methods=["OPTIONS"])
@app.route("/api/dashboard-data", methods=["OPTIONS"])
def handle_options():
    response = jsonify({"status": "ok"})
    origin = request.headers.get("Origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Cookie, Set-Cookie"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response, 200

## Main
if __name__ == "__main__":
    # Initialize attendance records for all users at startup
    initialize_attendance_records()
    app.run(host='0.0.0.0', port=5000, debug=True)
    #app.run(debug=True, port=5001)