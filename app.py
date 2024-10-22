from flask import Flask, jsonify, request # type: ignore
from pymongo import MongoClient
from dotenv import load_dotenv # type: ignore
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity # type: ignore
from datetime import datetime
from bson.objectid import ObjectId
import spacy # type: ignore

# Load environment variables
load_dotenv()

app = Flask(__name__)

# JWT Setup
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

# Connect to MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client['clinic_chatbot']  # Use the chatbot database

# Load spaCy NLP Model
nlp = spacy.load('en_core_web_sm')

# ----------- User Routes (Signup, Login) are unchanged ----------- #

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
            "_id": str(appt["_id"]),  # Convert ObjectId to string
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

# ----------- Prescription Routes ---------------- #

# Request a Prescription (Create)
@app.route('/prescriptions', methods=['POST'])
@jwt_required()
def request_prescription():
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    data = request.get_json()

    prescription = {
        "patient_email": current_user["email"],
        "doctor": data["doctor"],
        "medication": data["medication"],
        "status": "pending",
        "request_date": datetime.utcnow(),
        "approval_date": None
    }

    db.prescriptions.insert_one(prescription)
    return jsonify({"message": "Prescription requested successfully!"}), 201

# View User's Prescriptions (Read)
@app.route('/prescriptions', methods=['GET'])
@jwt_required()
def view_prescriptions():
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    prescriptions = db.prescriptions.find({"patient_email": current_user["email"]})

    prescription_list = []
    for prescription in prescriptions:
        prescription_list.append({
            "_id": str(prescription["_id"]),  # Convert ObjectId to string
            "doctor": prescription["doctor"],
            "medication": prescription["medication"],
            "status": prescription["status"],
            "request_date": prescription["request_date"],
            "approval_date": prescription["approval_date"]
        })

    return jsonify(prescription_list), 200

# Update Prescription Status (Approve, Renew, or Cancel)
@app.route('/prescriptions/<prescription_id>', methods=['PUT'])
@jwt_required()
def update_prescription(prescription_id):
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    data = request.get_json()

    # Allow only the doctor (or an admin) to update the prescription status
    result = db.prescriptions.update_one(
        {"_id": ObjectId(prescription_id), "doctor": data["doctor"]},
        {"$set": {"status": data["status"], "approval_date": datetime.utcnow() if data["status"] == "approved" else None}}
    )

    if result.matched_count > 0:
        return jsonify({"message": "Prescription updated successfully!"}), 200
    return jsonify({"error": "Prescription not found or unauthorized access"}), 404

# Cancel a Prescription Request (Delete)
@app.route('/prescriptions/<prescription_id>', methods=['DELETE'])
@jwt_required()
def cancel_prescription(prescription_id):
    current_user = get_jwt_identity()  # Get the email of the logged-in user

    result = db.prescriptions.delete_one(
        {"_id": ObjectId(prescription_id), "patient_email": current_user["email"]}
    )

    if result.deleted_count > 0:
        return jsonify({"message": "Prescription canceled successfully!"}), 200
    return jsonify({"error": "Prescription not found or unauthorized access"}), 404

# ----------- Conversational Flow Handler ----------- #

@app.route('/chat', methods=['POST'])
@jwt_required()
def chat():
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    user_input = request.get_json().get('message', '')

    # Process the user's message using spaCy NLP
    doc = nlp(user_input.lower())

    # Basic intent detection using keyword matching
    if 'appointment' in user_input:
        return handle_appointment_request(doc, current_user)
    elif 'prescription' in user_input or 'medication' in user_input:
        return handle_prescription_request(doc, current_user)
    else:
        return jsonify({"message": "Sorry, I don't understand your request."}), 400

def handle_appointment_request(doc, current_user):
    # Try to find the doctor and date in the user's input
    doctor = None
    date = None

    for ent in doc.ents:
        if ent.label_ == 'PERSON':
            doctor = ent.text
        elif ent.label_ == 'DATE':
            date = ent.text

    if doctor and date:
        appointment = {
            "patient_email": current_user["email"],
            "doctor": doctor,
            "date": date,
            "status": "scheduled"
        }
        db.appointments.insert_one(appointment)
        return jsonify({"message": f"Appointment booked with {doctor} on {date}."}), 201
    else:
        return jsonify({"error": "Please provide the doctor's name and appointment date."}), 400

def handle_prescription_request(doc, current_user):
    # Try to find the doctor and medication in the user's input
    doctor = None
    medication = None

    for ent in doc.ents:
        if ent.label_ == 'PERSON':
            doctor = ent.text
        elif ent.label_ == 'ORG':  # Treat organization names as medication names for now
            medication = ent.text

    if doctor and medication:
        prescription = {
            "patient_email": current_user["email"],
            "doctor": doctor,
            "medication": medication,
            "status": "pending",
            "request_date": datetime.utcnow(),
            "approval_date": None
        }
        db.prescriptions.insert_one(prescription)
        return jsonify({"message": f"Prescription request for {medication} sent to {doctor}."}), 201
    else:
        return jsonify({"error": "Please provide the doctor's name and medication name."}), 400

if __name__ == '__main__':
    app.run(debug=True)
