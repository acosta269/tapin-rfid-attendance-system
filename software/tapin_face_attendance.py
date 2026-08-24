# tapin_face_attendance.py
"""
TapIn Attendance System - Face Recognition Dashboard
"""

import os
import sys
import json
import time
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import requests

# ============================================================================
# EXTERNAL STORAGE PATH CONFIGURATION
# ============================================================================
# This allows the storage folder to be accessed and edited even when compiled as EXE
# The storage folder should be in the same directory as the executable

def get_storage_path():
    """
    Get the storage path that works for both development and compiled EXE.
    When compiled as EXE, the storage folder should be in the same directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as Python script
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_dir, "storage")

# ============================================================================
# Configuration
# ============================================================================
API_URL = "https://tapin-api.up.railway.app"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Use external storage path that can be edited
STORAGE_DIR = get_storage_path()
ASSETS_DIR = os.path.join(STORAGE_DIR, "assets")
DATABASE_DIR = os.path.join(STORAGE_DIR, "database")
SAMPLES_DIR = os.path.join(STORAGE_DIR, "samples")
PROFILES_DIR = os.path.join(STORAGE_DIR, "profiles")
USERS_FILE = os.path.join(DATABASE_DIR, "users.json")

# ============================================================================
# Colors
# ============================================================================
COLORS = {
    "primary": "#2563EB",
    "primary_dark": "#1D4ED8",
    "primary_light": "#DBEAFE",
    "secondary": "#3B82F6",
    "accent": "#06B6D4",
    "accent_light": "#CFFAFE",
    "success": "#22C55E",
    "success_light": "#DCFCE7",
    "warning": "#F59E0B",
    "warning_light": "#FEF3C7",
    "danger": "#EF4444",
    "danger_light": "#FEE2E2",
    "info": "#3B82F6",
    "info_light": "#DBEAFE",
    "leave": "#8B5CF6",
    "leave_light": "#EDE9FE",
    "white": "#FFFFFF",
    "gray_50": "#F8FAFC",
    "gray_100": "#F1F5F9",
    "gray_200": "#E2E8F0",
    "gray_300": "#CBD5E1",
    "gray_400": "#94A3B8",
    "gray_500": "#64748B",
    "gray_600": "#475569",
    "gray_700": "#334155",
    "gray_800": "#1E293B",
    "gray_900": "#0F172A",
}

# ============================================================================
# Ensure Directories Exist
# ============================================================================
print(f"Storage Directory: {STORAGE_DIR}")
os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(SAMPLES_DIR, exist_ok=True)
os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# Create default users.json if not exists
if not os.path.exists(USERS_FILE):
    default_data = {"admin": [], "hr": [], "employees": []}
    with open(USERS_FILE, 'w') as f:
        json.dump(default_data, f, indent=4)
    print("Created default users.json")


class SimpleFaceAttendance:
    def __init__(self, root):
        self.root = root
        self.root.title("TapIn Attendance System - Face Recognition")
        self.root.geometry("1366x768")
        self.root.configure(bg=COLORS["gray_50"])
        self.root.resizable(False, False)

        self.is_running = False
        self.is_fullscreen = False
        self.camera = None
        self.recognizer = None
        self.face_cascade = None
        self.employees_data = {}
        self.last_attendance_time = {}
        self.attendance_cooldown = 5
        self.label_map = {}
        self.update_id = None
        self.logo_image = None
        self.canvas_width = 780
        self.canvas_height = 560
        self.camera_offset_x = 0
        self.camera_offset_y = 0

        # Load logo
        self.load_logo()

        self.load_employee_database()
        self.init_face_recognizer()
        self.create_widgets()
        self.start_camera()

    def load_logo(self):
        """Load logo from storage/assets/"""
        try:
            logo_paths = [
                os.path.join(ASSETS_DIR, "tapin_logo.png"),
                os.path.join(ASSETS_DIR, "tapin_logo.jpg"),
                os.path.join(ASSETS_DIR, "logo.png"),
                os.path.join(ASSETS_DIR, "logo.jpg"),
            ]
            
            for path in logo_paths:
                if os.path.exists(path):
                    img = Image.open(path)
                    img = img.resize((32, 32), Image.Resampling.LANCZOS)
                    self.logo_image = ImageTk.PhotoImage(img)
                    print(f"Loaded logo from: {path}")
                    return
            
            print("No logo found in storage/assets/")
        except Exception as e:
            print(f"Error loading logo: {e}")

    def load_employee_database(self):
        """Load employee database from users.json"""
        try:
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, 'r') as f:
                    data = json.load(f)
                    self.employees_data = {}
                    for category in ["admin", "hr", "employees"]:
                        if category in data:
                            for emp in data[category]:
                                uid = emp.get("uid")
                                if uid:
                                    self.employees_data[uid] = emp
                print(f"Loaded {len(self.employees_data)} employees")
            else:
                print("Users file not found, creating empty database")
                default_data = {"admin": [], "hr": [], "employees": []}
                with open(USERS_FILE, 'w') as f:
                    json.dump(default_data, f, indent=4)
        except Exception as e:
            print(f"Error loading database: {e}")

    def init_face_recognizer(self):
        """Initialize OpenCV face detector and LBPH recognizer"""
        try:
            cascade_paths = [
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml',
                os.path.join(cv2.__path__[0], 'data', 'haarcascade_frontalface_default.xml'),
            ]
            
            for path in cascade_paths:
                if os.path.exists(path):
                    self.face_cascade = cv2.CascadeClassifier(path)
                    print(f"Loaded cascade from: {path}")
                    break
            
            if self.face_cascade is None:
                print("Warning: Could not load face cascade.")
                self.face_cascade = cv2.CascadeClassifier()
            
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            print("Face recognizer initialized")
            self.train_recognizer()
            
        except Exception as e:
            print(f"Error initializing face recognizer: {e}")
            self.face_cascade = None
            self.recognizer = None

    def train_recognizer(self):
        """Train the LBPH recognizer using sample images"""
        faces = []
        labels = []
        label_map = {}

        if not os.path.exists(SAMPLES_DIR):
            print("Samples directory not found")
            return

        label_id = 0
        for emp_uid in os.listdir(SAMPLES_DIR):
            emp_folder = os.path.join(SAMPLES_DIR, emp_uid)
            if not os.path.isdir(emp_folder):
                continue

            employee = self.employees_data.get(emp_uid)
            if not employee:
                for uid, emp in self.employees_data.items():
                    if emp.get("employeeid") == emp_uid:
                        employee = emp
                        emp_uid = uid
                        break

            if not employee:
                print(f"Warning: No employee data found for folder: {emp_uid}")
                continue

            label_map[label_id] = {
                "uid": emp_uid,
                "name": f"{employee.get('firstname', '')} {employee.get('lastname', '')}".strip(),
                "emp_id": employee.get('employeeid', ''),
                "role": employee.get('role', 'employee')
            }

            for file in os.listdir(emp_folder):
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    img_path = os.path.join(emp_folder, file)
                    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                    if img is not None and self.face_cascade is not None:
                        faces_detected = self.face_cascade.detectMultiScale(img, 1.3, 5)
                        for (x, y, w, h) in faces_detected:
                            face = img[y:y+h, x:x+w]
                            face = cv2.resize(face, (100, 100))
                            faces.append(face)
                            labels.append(label_id)
                            print(f"  Training on: {file} for {label_map[label_id]['name']}")

            label_id += 1

        if faces and self.recognizer is not None:
            self.recognizer.train(faces, np.array(labels))
            self.label_map = label_map
            print(f"Trained on {len(faces)} faces for {len(label_map)} employees")
        else:
            print("No training data found or recognizer not initialized")

    def create_widgets(self):
        """Create GUI widgets with blue theme"""
        # Top Header
        header_frame = tk.Frame(self.root, bg=COLORS["primary"], height=60)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        # Logo
        if self.logo_image:
            logo_label = tk.Label(header_frame, image=self.logo_image, 
                                 bg=COLORS["primary"])
            logo_label.pack(side=tk.LEFT, padx=(15, 5), pady=10)

        header_title = tk.Label(header_frame, text="TapIn Attendance System", 
                               font=("Segoe UI", 18, "bold"), 
                               bg=COLORS["primary"], fg="white")
        header_title.pack(side=tk.LEFT, padx=(5, 10), pady=10)

        header_sub = tk.Label(header_frame, text="Face Recognition Dashboard", 
                             font=("Segoe UI", 11), 
                             bg=COLORS["primary"], fg=COLORS["accent_light"])
        header_sub.pack(side=tk.LEFT, padx=10, pady=10)

        # Status indicator
        self.status_indicator = tk.Label(header_frame, text="● Ready", 
                                        font=("Segoe UI", 10, "bold"),
                                        bg=COLORS["primary"], fg=COLORS["success_light"])
        self.status_indicator.pack(side=tk.RIGHT, padx=10, pady=10)

        # Fullscreen toggle button
        fullscreen_btn = tk.Button(header_frame, text="⛶ Fullscreen", 
                                   command=self.toggle_fullscreen,
                                   font=("Segoe UI", 9, "bold"),
                                   bg=COLORS["primary_dark"], fg="white",
                                   padx=12, pady=4, relief=tk.FLAT, cursor="hand2")
        fullscreen_btn.pack(side=tk.RIGHT, padx=10, pady=10)

        # Main container
        main_frame = tk.Frame(self.root, bg=COLORS["gray_50"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Left side - Camera feed
        left_frame = tk.Frame(main_frame, bg=COLORS["white"], relief=tk.RAISED, bd=1)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Camera header
        cam_header = tk.Frame(left_frame, bg=COLORS["primary_light"], height=35)
        cam_header.pack(fill=tk.X, side=tk.TOP)
        cam_header.pack_propagate(False)

        cam_label = tk.Label(cam_header, text="📷 Live Camera Feed", 
                            font=("Segoe UI", 11, "bold"),
                            bg=COLORS["primary_light"], fg=COLORS["primary_dark"])
        cam_label.pack(side=tk.LEFT, padx=12, pady=5)

        # Create a frame to center the camera
        cam_container = tk.Frame(left_frame, bg=COLORS["gray_100"])
        cam_container.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.cam_canvas = tk.Canvas(cam_container, bg=COLORS["gray_100"], 
                                   width=self.canvas_width, height=self.canvas_height,
                                   highlightthickness=0)
        self.cam_canvas.pack(expand=True)

        # Camera status bar
        cam_status_frame = tk.Frame(left_frame, bg=COLORS["gray_100"], height=30)
        cam_status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        cam_status_frame.pack_propagate(False)

        self.status_label = tk.Label(cam_status_frame, text="Ready", 
                                    font=("Segoe UI", 9),
                                    bg=COLORS["gray_100"], fg=COLORS["gray_600"])
        self.status_label.pack(side=tk.LEFT, padx=12, pady=5)

        # Control buttons
        btn_frame = tk.Frame(left_frame, bg=COLORS["white"])
        btn_frame.pack(pady=10)

        self.start_btn = tk.Button(btn_frame, text="▶ Start", command=self.start_system,
                                   font=("Segoe UI", 10, "bold"), 
                                   bg=COLORS["success"], fg="white",
                                   padx=25, pady=6, relief=tk.FLAT, cursor="hand2")
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(btn_frame, text="⏹ Stop", command=self.stop_system,
                                  font=("Segoe UI", 10, "bold"), 
                                  bg=COLORS["danger"], fg="white",
                                  padx=25, pady=6, relief=tk.FLAT, cursor="hand2", state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.reload_btn = tk.Button(btn_frame, text="⟳ Reload", command=self.reload_data,
                                    font=("Segoe UI", 10, "bold"), 
                                    bg=COLORS["info"], fg="white",
                                    padx=20, pady=6, relief=tk.FLAT, cursor="hand2")
        self.reload_btn.pack(side=tk.LEFT, padx=5)

        # Right side - Employee info
        right_frame = tk.Frame(main_frame, bg=COLORS["white"], relief=tk.RAISED, bd=1, width=380)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))
        right_frame.pack_propagate(False)

        # Employee photo
        photo_frame = tk.Frame(right_frame, bg=COLORS["white"])
        photo_frame.pack(fill=tk.X, padx=15, pady=15)

        photo_header = tk.Frame(photo_frame, bg=COLORS["primary_light"], height=30)
        photo_header.pack(fill=tk.X)
        photo_header.pack_propagate(False)

        tk.Label(photo_header, text="👤 Employee Photo", 
                font=("Segoe UI", 10, "bold"),
                bg=COLORS["primary_light"], fg=COLORS["primary_dark"]).pack(side=tk.LEFT, padx=10, pady=3)

        self.photo_canvas = tk.Canvas(photo_frame, bg=COLORS["gray_100"], width=180, height=180)
        self.photo_canvas.pack(pady=10, padx=10)
        self.photo_canvas.create_text(90, 90, text="No Face", font=("Segoe UI", 16), fill=COLORS["gray_400"])

        self.photo_label = tk.Label(photo_frame, text="No face detected", 
                                   font=("Segoe UI", 9),
                                   bg=COLORS["white"], fg=COLORS["gray_500"])
        self.photo_label.pack(pady=5)

        # Employee details
        details_frame = tk.Frame(right_frame, bg=COLORS["white"])
        details_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        details_header = tk.Frame(details_frame, bg=COLORS["primary_light"], height=30)
        details_header.pack(fill=tk.X)
        details_header.pack_propagate(False)

        tk.Label(details_header, text="📋 Employee Details", 
                font=("Segoe UI", 10, "bold"),
                bg=COLORS["primary_light"], fg=COLORS["primary_dark"]).pack(side=tk.LEFT, padx=10, pady=3)

        self.details_text = tk.Text(details_frame, font=("Segoe UI", 9), 
                                    bg=COLORS["gray_50"], fg=COLORS["gray_700"],
                                    wrap=tk.WORD, height=9, 
                                    relief=tk.FLAT, bd=1, highlightthickness=0)
        self.details_text.pack(fill=tk.BOTH, expand=True, pady=10)
        self.details_text.insert(tk.END, "Waiting for face detection...")
        self.details_text.config(state=tk.DISABLED)

        # Attendance log
        log_frame = tk.Frame(right_frame, bg=COLORS["white"])
        log_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        log_header = tk.Frame(log_frame, bg=COLORS["primary_light"], height=30)
        log_header.pack(fill=tk.X)
        log_header.pack_propagate(False)

        tk.Label(log_header, text="📝 Recent Attendance", 
                font=("Segoe UI", 10, "bold"),
                bg=COLORS["primary_light"], fg=COLORS["primary_dark"]).pack(side=tk.LEFT, padx=10, pady=3)

        self.log_listbox = tk.Listbox(log_frame, font=("Segoe UI", 9), 
                                      bg=COLORS["gray_50"], fg=COLORS["gray_700"],
                                      height=4, selectmode=tk.SINGLE,
                                      relief=tk.FLAT, bd=1, highlightthickness=0)
        self.log_listbox.pack(fill=tk.BOTH, expand=True, pady=10)

        # Bind escape key to exit fullscreen
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.root.bind("<F11>", self.toggle_fullscreen)

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode"""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        """Enter fullscreen mode"""
        self.root.attributes('-fullscreen', True)
        self.is_fullscreen = True

    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        self.root.attributes('-fullscreen', False)
        self.is_fullscreen = False
        self.root.geometry("1366x768")

    def start_camera(self):
        """Initialize camera"""
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                print("Could not open camera")
                return
            
            # Get actual camera resolution
            width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate center offset to fit canvas
            self.camera_offset_x = max(0, (width - self.canvas_width) // 2)
            self.camera_offset_y = max(0, (height - self.canvas_height) // 2)
            
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.is_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_indicator.config(text="● Running", fg=COLORS["success"])
            self.update_camera_feed()
        except Exception as e:
            print(f"Camera error: {e}")
            messagebox.showerror("Camera Error", "Could not access camera.")

    def update_camera_feed(self):
        """Update camera feed in canvas with mirror effect and centering"""
        if not self.is_running or self.camera is None:
            return

        try:
            ret, frame = self.camera.read()
            if ret:
                # Mirror the frame horizontally
                frame = cv2.flip(frame, 1)
                
                # Get frame dimensions
                h, w = frame.shape[:2]
                
                # Calculate center crop to match canvas
                if w > self.canvas_width:
                    start_x = (w - self.canvas_width) // 2
                    frame = frame[:, start_x:start_x + self.canvas_width]
                
                if h > self.canvas_height:
                    start_y = (h - self.canvas_height) // 2
                    frame = frame[start_y:start_y + self.canvas_height, :]
                
                # Resize to fit canvas if needed
                if frame.shape[1] != self.canvas_width or frame.shape[0] != self.canvas_height:
                    frame = cv2.resize(frame, (self.canvas_width, self.canvas_height))
                
                # Process frame for face recognition
                processed_frame, detected_info = self.process_frame(frame)

                # Convert to RGB for display
                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                img_tk = ImageTk.PhotoImage(img)

                self.cam_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                self.cam_canvas.image = img_tk

                if detected_info:
                    self.status_label.config(text=f"Detected: {detected_info['name']}", 
                                            fg=COLORS["primary"])
                else:
                    self.status_label.config(text="No faces detected", 
                                            fg=COLORS["gray_500"])

            self.update_id = self.root.after(50, self.update_camera_feed)
        except Exception as e:
            print(f"Update error: {e}")
            self.root.after(100, self.update_camera_feed)

    def process_frame(self, frame):
        """Process frame for face recognition"""
        if self.face_cascade is None:
            return frame, None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        detected_info = None

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            face = cv2.resize(face, (100, 100))
            cv2.rectangle(frame, (x, y), (x+w, y+h), COLORS["primary"], 2)

            if self.recognizer is not None:
                try:
                    label, confidence = self.recognizer.predict(face)
                    if confidence < 70 and label in self.label_map:
                        info = self.label_map[label]
                        name = info['name']
                        emp_uid = info['uid']
                        emp_id = info['emp_id']
                        role = info['role']

                        cv2.rectangle(frame, (x, y-25), (x+w, y), COLORS["primary"], cv2.FILLED)
                        cv2.putText(frame, name, (x+6, y-6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

                        detected_info = {
                            'name': name,
                            'uid': emp_uid,
                            'emp_id': emp_id,
                            'role': role
                        }

                        self.update_employee_details(emp_uid, name, emp_id, role)
                        self.check_and_record_attendance(emp_uid, name, emp_id, role)
                except Exception as e:
                    print(f"Recognition error: {e}")
                    cv2.putText(frame, "Unknown", (x+6, y-6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 1)
            else:
                cv2.putText(frame, "No Recognizer", (x+6, y-6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 1)

        return frame, detected_info

    def check_and_record_attendance(self, emp_uid, name, emp_id, role):
        """Check if attendance should be recorded"""
        current_time = time.time()
        if emp_uid in self.last_attendance_time:
            if current_time - self.last_attendance_time[emp_uid] < self.attendance_cooldown:
                return

        self.last_attendance_time[emp_uid] = current_time
        self.send_attendance_to_api(emp_uid, name, emp_id, role)

    def send_attendance_to_api(self, emp_uid, name, emp_id, role):
        """Send attendance data to API"""
        try:
            employee = self.employees_data.get(emp_uid, {})
            rfid = employee.get("rfid", "")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            url = f"{API_URL}/api/receive-rfid"
            response = requests.post(url, json={"rfid": rfid, "scanned_at": timestamp}, timeout=10)

            if response.status_code == 200:
                log_entry = f"[{timestamp}] ✓ {name} ({emp_id}) - Recorded"
                self.log_listbox.insert(0, log_entry)
                print(f"Attendance recorded for {name} at {timestamp}")
                self.status_indicator.config(text="● Recorded!", fg=COLORS["success"])
                self.root.after(2000, lambda: self.status_indicator.config(text="● Running", fg=COLORS["success"]))
            else:
                log_entry = f"[{timestamp}] ✗ {name} ({emp_id}) - API error: {response.status_code}"
                self.log_listbox.insert(0, log_entry)
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] ✗ {name} ({emp_id}) - Connection error"
            self.log_listbox.insert(0, log_entry)

    def update_employee_details(self, emp_uid, name, emp_id, role):
        """Update employee details display"""
        employee = self.employees_data.get(emp_uid, {})
        if employee:
            details = f"""
Employee ID:  {employee.get('employeeid', 'N/A')}
Name:         {employee.get('firstname', '')} {employee.get('lastname', '')}
Role:         {employee.get('role', 'employee').upper()}
Address:      {employee.get('address', 'N/A')}
Contact:      {employee.get('cpnumber', 'N/A')}
Email:        {employee.get('email', 'N/A')}
Status:       ✅ RECOGNIZED
Time:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, details)
            self.details_text.config(state=tk.DISABLED)

            image_path = employee.get("image", "")
            if image_path:
                full_path = os.path.join(BASE_DIR, image_path)
                if os.path.exists(full_path):
                    try:
                        img = Image.open(full_path)
                        img = img.resize((180, 180), Image.Resampling.LANCZOS)
                        img_tk = ImageTk.PhotoImage(img)
                        self.photo_canvas.delete("all")
                        self.photo_canvas.create_image(90, 90, anchor=tk.CENTER, image=img_tk)
                        self.photo_canvas.image = img_tk
                        self.photo_label.config(text=f"{name}", fg=COLORS["primary"])
                    except Exception as e:
                        print(f"Error loading photo: {e}")
                        self.show_default_photo(name)
                else:
                    self.show_default_photo(name)
            else:
                self.show_default_photo(name)
        else:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"Face detected: {name}\nEmployee ID: {emp_id}\nStatus: Unregistered")
            self.details_text.config(state=tk.DISABLED)
            self.photo_canvas.delete("all")
            self.photo_canvas.create_text(90, 90, text="?", font=("Segoe UI", 60), fill=COLORS["gray_400"])
            self.photo_label.config(text="Unknown Person", fg=COLORS["danger"])

    def show_default_photo(self, name):
        """Show default photo icon"""
        self.photo_canvas.delete("all")
        self.photo_canvas.create_text(90, 90, text="👤", font=("Segoe UI", 60))
        self.photo_label.config(text=f"{name}", fg=COLORS["primary"])

    def start_system(self):
        """Start the attendance system - full restart"""
        self.stop_system()
        self.cam_canvas.delete("all")
        self.last_attendance_time = {}
        self.start_camera()

    def stop_system(self):
        """Stop the attendance system - full stop"""
        self.is_running = False
        if self.update_id:
            self.root.after_cancel(self.update_id)
            self.update_id = None
        
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_indicator.config(text="● Stopped", fg=COLORS["danger"])
        self.status_label.config(text="System stopped", fg=COLORS["gray_500"])
        self.cam_canvas.delete("all")
        print("System stopped")

    def reload_data(self):
        """Reload database and retrain"""
        self.load_employee_database()
        self.init_face_recognizer()
        if self.recognizer is not None:
            messagebox.showinfo("Reload Complete", 
                               f"Loaded {len(self.employees_data)} employees\n"
                               f"Trained {len(self.label_map)} face models")
        else:
            messagebox.showinfo("Reload Complete", "Database reloaded but recognizer not initialized")

    def on_closing(self):
        """Clean up on window close"""
        self.is_running = False
        if self.update_id:
            self.root.after_cancel(self.update_id)
        if self.camera:
            self.camera.release()
        self.root.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = SimpleFaceAttendance(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()