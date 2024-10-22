from flask import Flask, jsonify, request # type: ignore
from pymongo import MongoClient
from dotenv import load_dotenv # type: ignore
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Connect to MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client['clinic_chatbot']  # Use the chatbot database

# Home route for testing
@app.route('/')
def home():
    return jsonify({"message": "Welcome to the AI-Powered Clinical Chatbot!"})

if __name__ == '__main__':
    app.run(debug=True)
