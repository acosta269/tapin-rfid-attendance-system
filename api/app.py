import os
import time
import json
import requests
import threading



from flask import Flask, jsonify, request
from datetime import datetime, timedelta

# Variables
app = Flask(__name__)


# temporary variables
latest_scan = {
    "rfid_id": None,
    "scanned_at": None
}

# Functions


# Routes
@app.route("/api/receive-rfid", methods=["POST"])
def receive_rfid():
    try:
        data = request.get_json()
        if not data or "rfid_id" not in data:
            return jsonify({
                "status": "error",
                "message": "Missing 'rfid_id' in request body"
            }), 400

        rfid_id = str(data["rfid_id"]).strip()
        if not rfid_id:
            return jsonify({
                "status": "error",
                "message": "rfid_id cannot be empty"
            }), 400

        latest_scan["rfid_id"] = rfid_id
        latest_scan["scanned_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print("Received RFID:", rfid_id)
        return jsonify({
            "status": "success",
            "message": "RFID ID received",
            "data": latest_scan
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/api/get-latest-rfid", methods=["GET"])
def get_latest_rfid():
    return jsonify({
        "status": "success",
        "data": latest_scan
    }), 200

# Error Handling
@app.errorhandler(404)
def page_not_found(e):
    timestamp = datetime.now().isoformat()
    return Response.error('Invalid request', '', timestamp)

# Main
if __name__ == '__main__':
    app.run()  # Run the app
    #app.run(debug=True,port=5001)  # for debug