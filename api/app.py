## Imports
import os
import time
import json
import requests
import threading

from flask import Flask, jsonify, request, Response
from datetime import datetime, timedelta

## Variables
app = Flask(__name__)

## Temporary variables
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

## Routes
# Device ping route
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

        print(f"Ping received from {device_id} | Last seen: {now}")
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

# Employee registration route
@app.route("/api/register-employee", methods=["POST"])
def register_employee():
    try:
        data = request.get_json()

        required = ["employeeid", "rfid", "lastname", "firstname", "address", "bdate", "cpnumber", "email"]
        if not data or not all(key in data for key in required):
            return jsonify({
                "status": "error",
                "message": "Missing required fields",
                "required_fields": required
            }), 400

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        latest_employee["uid"] = data.get("rfid")
        latest_employee["employeeid"] = str(data.get("employeeid", "")).strip()
        latest_employee["rfid"] = str(data.get("rfid", "")).strip()
        latest_employee["lastname"] = str(data.get("lastname", "")).strip()
        latest_employee["firstname"] = str(data.get("firstname", "")).strip()
        latest_employee["address"] = str(data.get("address", "")).strip()
        latest_employee["bdate"] = str(data.get("bdate", "")).strip()
        latest_employee["cpnumber"] = str(data.get("cpnumber", "")).strip()
        latest_employee["email"] = str(data.get("email", "")).strip()
        latest_employee["image"] = data.get("image")
        latest_employee["timestamp_creation"] = now
        latest_employee["timestamp_modified"] = now

        print("Registered:", latest_employee['firstname'], latest_employee['lastname'], "RFID:", latest_employee['rfid'])

        return jsonify({
            "status": "success",
            "message": "Employee registered successfully",
            "data": latest_employee
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Registration failed: " + str(e)
        }), 500

# RFID receiving route
@app.route("/api/receive-rfid", methods=["POST"])
def receive_rfid():
    try:
        data = request.get_json()
        if not data or "rfid" not in data:
            return jsonify({
                "status": "error",
                "message": "Missing 'rfid' in request body"
            }), 400

        rfid = str(data["rfid"]).strip()
        if not rfid:
            return jsonify({
                "status": "error",
                "message": "rfid cannot be empty"
            }), 400

        latest_scan["rfid"] = rfid
        latest_scan["scanned_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print("Received RFID:", rfid)
        return jsonify({
            "status": "success",
            "message": "RFID received",
            "data": latest_scan
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

# Device status check route
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

# Fetch latest RFID route
@app.route("/api/get-latest-rfid", methods=["GET"])
def get_latest_rfid():
    return jsonify({
        "status": "success",
        "rfid": latest_scan["rfid"],
        "scanned_at": latest_scan["scanned_at"],
        "data": latest_scan
    }), 200

# Error Handling
@app.errorhandler(404)
def page_not_found(e):
    timestamp = datetime.now().isoformat()
    return jsonify({
        "status": "error",
        "message": "Invalid request",
        "timestamp": timestamp
    }), 404

## Main
if __name__ == '__main__':
    app.run()
    #app.run(debug=True, port=5001)