from datetime import timezone
from transformers import pipeline
from flask import Flask, jsonify, request
from pymongo import MongoClient
from dotenv import load_dotenv # type: ignore
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity # type: ignore
import socketio
from datetime import datetime
from bson.objectid import ObjectId
import spacy # type: ignore
from flask_socketio import SocketIO, emit

# Load environment variables
load_dotenv()

from flask_cors import CORS

app = Flask(__name__)

# Enable CORS for all routes and allow localhost:8000
CORS(app, resources={r"/*": {"origins": "http://localhost:8000"}})

# Initialize Flask-SocketIO and allow WebSocket connections from localhost:8000
socketio = SocketIO(app, cors_allowed_origins="http://localhost:8000")

# JWT Setup
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

# Connect to MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client['clinic_chatbot']  # Use the chatbot database

# Load BERT Model for Intent Recognition
classifier = pipeline('sentiment-analysis')

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

    appointment_list = [
        {
            "_id": str(appt["_id"]),  # Convert ObjectId to string
            "doctor": appt["doctor"],
            "date": appt["date"],
            "status": appt["status"],
        }
        for appt in appointments
    ]
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
        "request_date": datetime.now(timezone.utc),
        "approval_date": None,
    }

    db.prescriptions.insert_one(prescription)
    return jsonify({"message": "Prescription requested successfully!"}), 201

# View User's Prescriptions (Read)
@app.route('/prescriptions', methods=['GET'])
@jwt_required()
def view_prescriptions():
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    prescriptions = db.prescriptions.find({"patient_email": current_user["email"]})

    prescription_list = [
        {
            "_id": str(prescription["_id"]),  # Convert ObjectId to string
            "doctor": prescription["doctor"],
            "medication": prescription["medication"],
            "status": prescription["status"],
            "request_date": prescription["request_date"],
            "approval_date": prescription["approval_date"],
        }
        for prescription in prescriptions
    ]
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
        {
            "$set": {
                "status": data["status"],
                "approval_date": (
                    datetime.now(timezone.utc)
                    if data["status"] == "approved"
                    else None
                ),
            }
        },
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

# @app.route('/chat', methods=['POST'])
# @jwt_required()
# def chat():
#     current_user = get_jwt_identity()  # Get the email of the logged-in user
#     user_input = request.get_json().get('message', '')

#     # Process the user's message using spaCy NLP
#     doc = nlp(user_input.lower())

#     # Basic intent detection using keyword matching
#     if 'appointment' in user_input:
#         return handle_appointment_request(doc, current_user)
#     elif 'prescription' in user_input or 'medication' in user_input:
#         return handle_prescription_request(doc, current_user)
#     else:
#         return jsonify({"message": "Sorry, I don't understand your request."}), 400

# def handle_appointment_request(doc, current_user):
#     # Try to find the doctor and date in the user's input
#     doctor = None
#     date = None

#     for ent in doc.ents:
#         if ent.label_ == 'PERSON':
#             doctor = ent.text
#         elif ent.label_ == 'DATE':
#             date = ent.text

#     if doctor and date:
#         appointment = {
#             "patient_email": current_user["email"],
#             "doctor": doctor,
#             "date": date,
#             "status": "scheduled"
#         }
#         db.appointments.insert_one(appointment)
#         return jsonify({"message": f"Appointment booked with {doctor} on {date}."}), 201
#     else:
#         return jsonify({"error": "Please provide the doctor's name and appointment date."}), 400

# def handle_prescription_request(doc, current_user):
#     # Try to find the doctor and medication in the user's input
#     doctor = None
#     medication = None

#     for ent in doc.ents:
#         if ent.label_ == 'PERSON':
#             doctor = ent.text
#         elif ent.label_ == 'ORG':  # Treat organization names as medication names for now
#             medication = ent.text

#     if doctor and medication:
#         prescription = {
#             "patient_email": current_user["email"],
#             "doctor": doctor,
#             "medication": medication,
#             "status": "pending",
#             "request_date": datetime.now(timezone.utc),
#             "approval_date": None,
#         }
#         db.prescriptions.insert_one(prescription)
#         return jsonify({"message": f"Prescription request for {medication} sent to {doctor}."}), 201
#     else:
#         return jsonify({"error": "Please provide the doctor's name and medication name."}), 400

# if __name__ == '__main__':
#     app.run(debug=True)


# ----------- Conversational Flow with BERT Integration ----------- #

@app.route('/chat', methods=['POST'])
@jwt_required()
def chat():
    current_user = get_jwt_identity()  # Get the email of the logged-in user
    user_input = request.get_json().get('message', '')

    # Use BERT for intent recognition
    intent_result = classifier(user_input)
    intent = intent_result[0]['label'].lower()

    if 'appointment' in intent:
        return handle_appointment_request(user_input, current_user)
    elif 'prescription' in intent:
        return handle_prescription_request(user_input, current_user)
    else:
        return jsonify({"message": "Sorry, I don't understand your request."}), 400

def handle_appointment_request(user_input, current_user):
    # Extract doctor and date from user_input (extend this logic as needed)
    doctor = "Dr. John Smith"  # Hardcoded for now; expand with NLP
    date = "2024-10-30"  # Extract from user input

    appointment = {
        "patient_email": current_user["email"],
        "doctor": doctor,
        "date": date,
        "status": "scheduled"
    }
    db.appointments.insert_one(appointment)
    return jsonify({"message": f"Appointment booked with {doctor} on {date}."}), 201

def handle_prescription_request(user_input, current_user):
    # Extract doctor and medication from user_input (extend this logic)
    doctor = "Dr. John Smith"  # Hardcoded for now; expand with NLP
    medication = "Amoxicillin"  # Extract from user input

    prescription = {
        "patient_email": current_user["email"],
        "doctor": doctor,
        "medication": medication,
        "status": "pending",
        "request_date": datetime.now(timezone.utc),
        "approval_date": None,
    }
    db.prescriptions.insert_one(prescription)
    return jsonify({"message": f"Prescription request for {medication} sent to {doctor}."}), 201

# ----------- WebSocket Event for Real-Time Chat ----------- #

@socketio.on('message')
def handle_message(message):
    user_email = message['user_email']
    user_input = message['text']

    # Process user input using spaCy or advanced NLP models
    doc = nlp(user_input.lower())

    if 'appointment' in user_input:
        doctor = "Dr. John Smith"  # Example logic; expand later
        date = "2024-10-30"
        response = f"Appointment booked with {doctor} on {date}."
    elif 'prescription' in user_input:
        doctor = "Dr. John Smith"
        medication = "Amoxicillin"
        response = f"Prescription request for {medication} sent to {doctor}."
    else:
        response = "Sorry, I don't understand your request."

    emit('response', {'message': response})

if __name__ == '__main__':
    socketio.run(app, host='localhost', port=5000, debug=True)