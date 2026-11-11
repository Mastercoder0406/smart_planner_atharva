#!/usr/bin/env python3
"""
Machine Learning Model Training for Smart Route Planner
Trains a model to predict obstacle occurrence probability based on time patterns.
"""

import sqlite3
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
import os
from datetime import datetime, timedelta
import random

def generate_synthetic_training_data(num_samples=10000):
    """Generate synthetic training data for obstacle prediction."""
    print(f"Generating {num_samples} synthetic training samples...")

    data = []

    for _ in range(num_samples):
        # Generate random time features
        hour = random.randint(0, 23)
        day_of_week = random.randint(0, 6)  # 0=Monday, 6=Sunday

        # Determine if it's rush hour
        is_rush_hour = 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0

        # Determine if it's weekend
        is_weekend = 1 if day_of_week >= 5 else 0

        # Generate obstacle probability based on patterns
        base_probability = 0.1  # Base 10% chance

        # Rush hour increases probability
        if is_rush_hour:
            base_probability += 0.2

        # Weekend mornings and evenings have different patterns
        if is_weekend:
            if 10 <= hour <= 16:
                base_probability += 0.1  # More activity on weekends
            elif hour >= 22 or hour <= 6:
                base_probability -= 0.05  # Less activity late night/early morning

        # Weekday patterns
        else:
            if 12 <= hour <= 14:
                base_probability += 0.05  # Lunch time
            elif hour >= 22 or hour <= 6:
                base_probability -= 0.08  # Less activity at night

        # Add some randomness
        obstacle_occurred = 1 if random.random() < base_probability else 0

        data.append({
            'hour': hour,
            'day_of_week': day_of_week,
            'is_rush_hour': is_rush_hour,
            'is_weekend': is_weekend,
            'obstacle_occurred': obstacle_occurred
        })

    df = pd.DataFrame(data)
    print(f"Generated {len(df)} samples")
    print(f"Obstacle occurrence rate: {df['obstacle_occurred'].mean():.3f}")

    return df

def train_obstacle_prediction_model():
    """Train and save the obstacle prediction model."""
    print("Starting ML model training...")

    # Generate synthetic training data
    df = generate_synthetic_training_data(50000)  # 50k samples for better training

    # Prepare features and target
    feature_cols = ['hour', 'day_of_week', 'is_rush_hour', 'is_weekend']
    X = df[feature_cols]
    y = df['obstacle_occurred']

    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print(f"Training set size: {len(X_train)}")
    print(f"Test set size: {len(X_test)}")

    # Train Logistic Regression model (as mentioned in the paper)
    print("Training Logistic Regression model...")
    lr_model = LogisticRegression(random_state=42, max_iter=1000)
    lr_model.fit(X_train, y_train)

    # Train Random Forest for comparison
    print("Training Random Forest model...")
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
    rf_model.fit(X_train, y_train)

    # Evaluate models
    models = {
        'Logistic Regression': lr_model,
        'Random Forest': rf_model
    }

    best_model = None
    best_score = 0
    best_model_name = None

    for name, model in models.items():
        # Predictions
        y_pred = model.predict(X_test)

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        print(f"\n{name} Performance:")
        print(f"  Accuracy: {accuracy:.4f}")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print(f"  F1 Score: {f1:.4f}")

        # Use accuracy for imbalanced dataset (since F1 is 0 due to class imbalance)
        if accuracy > best_score:
            best_score = accuracy
            best_model = model
            best_model_name = name

    print(f"\nBest model: {best_model_name} (Accuracy: {best_score:.4f})")

    # Save the best model
    model_filename = 'obstacle_predictor.pkl'
    joblib.dump(best_model, model_filename)
    print(f"Model saved as {model_filename}")

    # Save training data to database for future reference
    save_training_data_to_db(df)

    return best_model

def save_training_data_to_db(df):
    """Save training data to the database for future model updates."""
    print("Saving training data to database...")

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Clear existing training data
    cursor.execute('DELETE FROM ml_training_data')

    # Insert new training data
    current_time = int(datetime.now().timestamp())
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO ml_training_data
            (hour, day_of_week, is_rush_hour, is_weekend, obstacle_occurred, collected_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            int(row['hour']),
            int(row['day_of_week']),
            int(row['is_rush_hour']),
            int(row['is_weekend']),
            int(row['obstacle_occurred']),
            current_time
        ))

    conn.commit()
    conn.close()
    print(f"Saved {len(df)} training samples to database")

def load_existing_training_data():
    """Load existing training data from database."""
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT hour, day_of_week, is_rush_hour, is_weekend, obstacle_occurred FROM ml_training_data')
        rows = cursor.fetchall()
        conn.close()

        if rows:
            df = pd.DataFrame(rows, columns=['hour', 'day_of_week', 'is_rush_hour', 'is_weekend', 'obstacle_occurred'])
            print(f"Loaded {len(df)} existing training samples from database")
            return df
        else:
            print("No existing training data found")
            return None
    except Exception as e:
        print(f"Error loading existing training data: {e}")
        return None

def update_model_with_new_data():
    """Update the model with any new obstacle reports."""
    print("Checking for new obstacle data...")

    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Get obstacles reported in the last 24 hours that aren't in training data yet
        one_day_ago = int((datetime.now() - timedelta(days=1)).timestamp())
        cursor.execute('''
            SELECT lat, lng, reported_at, description
            FROM obstacles
            WHERE reported_at > ?
        ''', (one_day_ago,))

        new_obstacles = cursor.fetchall()
        conn.close()

        if not new_obstacles:
            print("No new obstacle data to add")
            return

        print(f"Found {len(new_obstacles)} new obstacle reports")

        # Convert to training data format
        new_training_data = []
        for obs in new_obstacles:
            reported_time = datetime.fromtimestamp(obs[2])
            hour = reported_time.hour
            day_of_week = reported_time.weekday()
            is_rush_hour = 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0
            is_weekend = 1 if day_of_week >= 5 else 0

            new_training_data.append({
                'hour': hour,
                'day_of_week': day_of_week,
                'is_rush_hour': is_rush_hour,
                'is_weekend': is_weekend,
                'obstacle_occurred': 1
            })

        if new_training_data:
            # Load existing model and retrain
            try:
                model = joblib.load('obstacle_predictor.pkl')
                print("Loaded existing model for retraining")

                # Load existing training data
                existing_df = load_existing_training_data()
                if existing_df is not None:
                    # Combine with new data
                    new_df = pd.DataFrame(new_training_data)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)

                    # Retrain model
                    feature_cols = ['hour', 'day_of_week', 'is_rush_hour', 'is_weekend']
                    X = combined_df[feature_cols]
                    y = combined_df['obstacle_occurred']

                    model.fit(X, y)
                    joblib.dump(model, 'obstacle_predictor.pkl')
                    print("Model retrained with new data")

                    # Save updated training data
                    save_training_data_to_db(combined_df)

            except FileNotFoundError:
                print("No existing model found. Run initial training first.")

    except Exception as e:
        print(f"Error updating model: {e}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "update":
        # Update existing model with new data
        update_model_with_new_data()
    else:
        # Train new model
        train_obstacle_prediction_model()