from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, flash, Response, make_response, abort
from io import StringIO
import pickle
import numpy as np
import pandas as pd
import uuid
from datetime import datetime
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import URLSafeSerializer
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId

# Load model and scaler
with open("models/churn_model.pkl", "rb") as model_file:
    model = pickle.load(model_file)

with open("models/scaler.pkl", "rb") as scaler_file:
    scaler = pickle.load(scaler_file)

# Feature names
feature_names = ['credit_score', 'age', 'tenure', 'balance', 'products_number', 
                 'credit_card', 'active_member', 'estimated_salary']

app = Flask(__name__)
app.secret_key = '@123456789'

# MongoDB Atlas connection
client = MongoClient("mongodb+srv://root:root@cluster0.b4j8abw.mongodb.net/")
db = client.churn_prediction
users_collection = db.users
predictions_collection = db.predictions

# Add this custom session interface
class SafeSessionInterface(SecureCookieSessionInterface):
    def get_signing_serializer(self, app):
        if not app.secret_key:
            return None
        return URLSafeSerializer(app.secret_key, salt='flask-session')
app.session_interface = SafeSessionInterface()

# Simple session size reduction (add this after creating 'app')
app.session_interface.serializer = pickle
app.session_interface.pickle_protocol = 2  # Makes session cookies smaller

feature_ranges = {
    'credit_score': (300, 850, 10),
    'age': (18, 80, 1),
    'balance': (0, 250000, 1000),
    'estimated_salary': (0, 200000, 1000)
}

@app.before_request
def require_login():
    allowed_routes = ['login', 'register', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        flash('Please login or register to access this content', 'info')
        return redirect(url_for('login'))

@app.route("/")
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Basic stats for dashboard
    stats = {
        'total_samples': 10000,
        'churn_rate': 0.20,
        'top_factors': {
            'balance': 0.45,
            'active_member': 0.32,
            'products_number': 0.28
        }
    }
    return render_template("index.html", stats=stats)

@app.route("/explorer")
def explorer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    defaults = {
        'credit_score': 650,
        'age': 35,
        'balance': 100000,
        'estimated_salary': 50000
    }
    return render_template("explorer.html", ranges=feature_ranges, defaults=defaults)

@app.route('/download_batch')
def download_batch():
    if 'batch_results' not in session:
        abort(404)
    
    csv_data = session['batch_results']
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=predictions.csv'}
    )

@app.after_request
def log_headers(response):
    app.logger.debug(f"Response headers size: {len(str(response.headers))}")
    return response

@app.route("/history")
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user_preds = list(predictions_collection.find({'user_id': user_id}).sort('timestamp', -1).limit(100))
    
    # Convert ObjectId to string for each prediction
    for pred in user_preds:
        pred['_id'] = str(pred['_id'])
    
    return render_template("history.html", predictions=user_preds)

@app.route('/save_batch_prediction', methods=['POST'])
def save_batch_prediction():
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        if 'batch_results' not in session:
            return jsonify({"error": "No batch results to save"}), 400

        # Get the CSV data from session
        csv_data = session['batch_results']
        df = pd.read_csv(StringIO(csv_data))
        
        # Create a summary of the batch prediction
        prediction_data = {
            'user_id': session['user_id'],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'prediction': 'Batch',
            'probability': float(df['Churn Probability'].mean()),
            'data': {
                'samples': len(df),
                'positive_predictions': int(df['Churn Prediction'].sum()),
                'average_probability': float(df['Churn Probability'].mean())
            },
            'type': 'batch'
        }
        
        # Insert into MongoDB
        result = predictions_collection.insert_one(prediction_data)
        
        return jsonify({"success": True, "prediction_id": str(result.inserted_id)})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/batch', methods=['GET', 'POST'])
def batch_predict():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
            
        try:
            # Read CSV and ensure string data
            df = pd.read_csv(file)
            # Convert all numeric columns to float
            for col in feature_names:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Process predictions
            scaled = scaler.transform(df[feature_names])
            df['Churn Probability'] = model.predict_proba(scaled)[:, 1]
            df['Churn Prediction'] = model.predict(scaled)
            
            # Store only what's necessary in session
            session['batch_results'] = df.to_csv(index=False)
            
            return render_template('batch.html', 
                                table=df.head(10).to_html(classes='table', index=False),
                                show_save_button=True)
            
        except Exception as e:
            flash(f'Error: {str(e)}')
            return redirect(request.url)
    
    return render_template('batch.html', show_save_button=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = users_collection.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        
        if users_collection.find_one({'email': email}):
            flash('Email already exists')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        user_data = {
            'email': email,
            'password': hashed_password,
            'created_at': datetime.now()
        }
        
        result = users_collection.insert_one(user_data)
        session['user_id'] = str(result.inserted_id)
        
        return redirect(url_for('home'))
    
    return render_template('register.html')

@app.context_processor
def inject_user_data():
    if 'user_id' in session:
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        return {'current_user': user}
    return {}

@app.route("/predict", methods=["POST"])
def predict():
    try:
        # Handle both form and JSON data
        if request.is_json:
            data = request.get_json()
            features = [float(data.get(key, 0)) for key in feature_names]
        else:
            features = [float(request.form.get(key, 0)) for key in feature_names]
        
        # Scale features
        scaled_features = scaler.transform([features])
        
        # Predict
        prediction = model.predict(scaled_features)[0]
        probability = model.predict_proba(scaled_features)[0][1]

        # Feature importance
        feature_importance = abs(model.coef_[0])
        feature_importance_dict = dict(zip(feature_names, feature_importance))

        return jsonify({
            "churn": int(prediction),
            "probability": round(float(probability), 4),
            "feature_importance": feature_importance_dict
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400
        
@app.route("/save_prediction", methods=["POST"])
def save_prediction():
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.form.to_dict()
        
        # Convert string values to appropriate types
        prediction_data = {
            'user_id': session['user_id'],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'prediction': data.get('prediction', 'No'),
            'probability': float(data.get('probability', 0)),
            'data': {
                'credit_score': int(data.get('credit_score', 0)),
                'age': int(data.get('age', 0)),
                'tenure': int(data.get('tenure', 0)),
                'balance': float(data.get('balance', 0)),
                'products_number': int(data.get('products_number', 0)),
                'credit_card': int(data.get('credit_card', 0)),
                'active_member': int(data.get('active_member', 0)),
                'estimated_salary': float(data.get('estimated_salary', 0))
            }
        }
        
        # Insert into MongoDB
        result = predictions_collection.insert_one(prediction_data)
        
        return jsonify({"success": True, "prediction_id": str(result.inserted_id)})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/logout")
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
