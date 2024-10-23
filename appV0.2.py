from transformers import pipeline
from flask import Flask, jsonify, request
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_socketio import SocketIO, emit
import socketio
from bson import ObjectId
from datetime import datetime
import spacy
from datetime import timezone

# Load environment variables
load_dotenv()

from flask_cors import CORS

app = Flask(__name__)
# Enable CORS and allow WebSocket connections from 'localhost'
CORS(app, resources={r"/*": {"origins": "http://localhost:5000"}})
sio = socketio.Server(cors_allowed_origins='*')
socketio = SocketIO(app)  # WebSocket integration Enable real-time communication


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
    socketio.run(app, debug=True)

# if __name__ == '__main__':
#     app.run(debug=True)
