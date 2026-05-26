import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import joblib
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineers new features based on Time and Amount."""
    logging.info("Engineering features...")
    df = df.copy()
    
    if 'Time' in df.columns:
        # hour_of_day
        df['hour_of_day'] = (df['Time'] / 3600) % 24
        
        # is_weekend
        # Time is elapsed seconds. Assuming day 0 is Monday, days 5 & 6 are weekend.
        df['day_of_week'] = (df['Time'] // 86400) % 7
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df.drop(columns=['day_of_week'], inplace=True)
    
    if 'Amount' in df.columns:
        # amount_zscore
        mean_amt = df['Amount'].mean()
        std_amt = df['Amount'].std()
        df['amount_zscore'] = (df['Amount'] - mean_amt) / std_amt
        
        # amount_log
        df['amount_log'] = np.log1p(df['Amount'])
        
        # high_value_flag (Assuming > 1000 is high value)
        df['high_value_flag'] = (df['Amount'] > 1000).astype(int)
    
    if 'Time' in df.columns:
        df.drop(columns=['Time'], inplace=True)
        logging.info("Dropped raw 'Time' column.")
        
    return df

def preprocess_data(data_path: str, models_dir: str):
    """Loads, engineers, splits, scales, and resamples the data."""
    logging.info(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    
    df = engineer_features(df)
    
    X = df.drop(columns=['Class'])
    y = df['Class']
    
    logging.info(f"Initial class distribution:\n{y.value_counts()}")
    
    # 70/15/15 Stratified Split
    # First split: 70% Train, 30% Temp (Val + Test)
    logging.info("Performing 70/15/15 stratified split...")
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42
    )
    
    # Second split: 15% Val, 15% Test (which is 50% of the Temp set)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=42
    )
    
    logging.info(f"Train shape: X={X_train.shape}, y={y_train.shape}")
    logging.info(f"Val shape:   X={X_val.shape}, y={y_val.shape}")
    logging.info(f"Test shape:  X={X_test.shape}, y={y_test.shape}")
    
    # Feature Scaling (Fit on Train only)
    logging.info("Fitting StandardScaler on training set only...")
    scaler = StandardScaler()
    
    # Fit and transform
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns)
    X_val_scaled = pd.DataFrame(scaler.transform(X_val), columns=X_val.columns)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=X_test.columns)
    
    # Save Scaler
    os.makedirs(models_dir, exist_ok=True)
    scaler_path = os.path.join(models_dir, "scaler.joblib")
    joblib.dump(scaler, scaler_path)
    logging.info(f"Saved fitted scaler to {scaler_path}")
    
    # Data Leakage Prevention: SMOTE on training set only
    logging.info("Applying SMOTE to the training set...")
    smote = SMOTE(random_state=42)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train)
    
    logging.info(f"Shape before SMOTE: {X_train_scaled.shape}")
    logging.info(f"Shape after SMOTE: {X_train_resampled.shape}")
    logging.info(f"Class distribution after SMOTE:\n{y_train_resampled.value_counts()}")
    
    return (X_train_resampled, y_train_resampled), (X_val_scaled, y_val), (X_test_scaled, y_test)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_path = os.path.join(base_dir, "data", "creditcard.csv")
    models_dir = os.path.join(base_dir, "models")
    preprocess_data(data_path, models_dir)
