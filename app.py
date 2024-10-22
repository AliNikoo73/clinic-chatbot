from flask import Flask, jsonify, request # type: ignore
from pymongo import MongoClient
from dotenv import load_dotenv # type: ignore
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity # type: ignore
from datetime import datetime
from bson.objectid import ObjectId

# Load environment variables
load_dotenv()

app = Flask(__name__)

# JWT Setup
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

# Connect to MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client['clinic_chatbot']  # Use the chatbot database

# User Signup Route
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if db.users.find_one({"email": data["email"]}):
        return jsonify({"error": "User already exists"}), 400

    db.users.insert_one({
        "email": data["email"],
        "password": data["password"]  # In a real-world app, hash this password!
    })
    return jsonify({"message": "User registered successfully!"}), 201

# User Login Route
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = db.users.find_one({"email": data["email"]})

    if user and user["password"] == data["password"]:  # In production, compare hashed passwords
        access_token = create_access_token(identity={"email": data["email"]})
        return jsonify(access_token=access_token), 200
    return jsonify({"error": "Invalid credentials"}), 401

# Protected Route Example
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(message="Access granted to protected route"), 200

# ----------- Appointment Routes ---------------- #

# Book an Appointment (Create)
@app.route('/appointments', methods=['POST'])
@jwt_required()
def book_appointment():
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    data = request.get_json()

    appointment = {
        "patient_email": current_user["email"],
        "doctor": data["doctor"],
        "date": data["date"],
        "status": "scheduled"
    }

    db.appointments.insert_one(appointment)
    return jsonify({"message": "Appointment booked successfully!"}), 201

# View User's Appointments (Read)
@app.route('/appointments', methods=['GET'])
@jwt_required()
def view_appointments():
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    appointments = db.appointments.find({"patient_email": current_user["email"]})

    appointment_list = []
    for appt in appointments:
        appointment_list.append({
            "doctor": appt["doctor"],
            "date": appt["date"],
            "status": appt["status"]
        })

    return jsonify(appointment_list), 200

# Update Appointment Status (Update)
@app.route('/appointments/<appointment_id>', methods=['PUT'])
@jwt_required()
def update_appointment(appointment_id):
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    data = request.get_json()

    result = db.appointments.update_one(
        {"_id": ObjectId(appointment_id), "patient_email": current_user["email"]},
        {"$set": {"status": data["status"]}}
    )

    if result.matched_count > 0:
        return jsonify({"message": "Appointment updated successfully!"}), 200
    return jsonify({"error": "Appointment not found"}), 404

# Cancel an Appointment (Delete)
@app.route('/appointments/<appointment_id>', methods=['DELETE'])
@jwt_required()
def cancel_appointment(appointment_id):
    current_user = get_jwt_identity()  # Get the email of the logged-in user

    result = db.appointments.delete_one(
        {"_id": ObjectId(appointment_id), "patient_email": current_user["email"]}
    )

    if result.deleted_count > 0:
        return jsonify({"message": "Appointment canceled successfully!"}), 200
    return jsonify({"error": "Appointment not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
