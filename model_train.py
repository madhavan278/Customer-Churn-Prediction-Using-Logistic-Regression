import pandas as pd
import numpy as np
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

def train_and_save_model():
    # 1. Load dataset
    try:
        df = pd.read_csv("datasets/BankCustomerData.csv")
        print("Dataset loaded successfully")
    except FileNotFoundError:
        print("Error: Dataset not found at 'datasets/BankCustomerData.csv'")
        print("Please ensure:")
        print("- You have the CSV file in the 'datasets' folder")
        print("- The file is named exactly 'BankCustomerData.csv'")
        return

    # 2. Feature selection
    feature_names = ['credit_score', 'age', 'tenure', 'balance', 'products_number', 
                    'credit_card', 'active_member', 'estimated_salary']
    X = df[feature_names]
    y = df['churn']

    # 3. Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 4. Feature Scaling
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # 5. Train Logistic Regression Model
    model = LogisticRegression()
    model.fit(X_train, y_train)

    # 6. Model Evaluation
    y_pred = model.predict(X_test)
    print("\nModel Evaluation:")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.2f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # 7. Save Model and Scaler
    os.makedirs("models", exist_ok=True)
    
    with open("models/churn_model.pkl", "wb") as model_file:
        pickle.dump(model, model_file)
    
    with open("models/scaler.pkl", "wb") as scaler_file:
        pickle.dump(scaler, scaler_file)
    
    print("\nModel files saved successfully:")
    print("- models/churn_model.pkl")
    print("- models/scaler.pkl")

if __name__ == "__main__":
    train_and_save_model()