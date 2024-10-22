from flask import Flask, jsonify, request # type: ignore
from pymongo import MongoClient
from dotenv import load_dotenv # type: ignore
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required # type: ignore

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

if __name__ == '__main__':
    app.run(debug=True)
