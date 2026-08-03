import os
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_recall_curve, auc, f1_score
import shap

def create_synthetic_data_if_missing(file_path="creditcard.csv"):
    if not os.path.exists(file_path):
        print("Dataset creditcard.csv not found. Generating mock dataset for initialization...")
        n_samples = 10000
        n_fraud = 20
        
        normal_data = np.random.randn(n_samples - n_fraud, 28)
        fraud_data = np.random.randn(n_fraud, 28) + 1.5
        
        V = np.vstack([normal_data, fraud_data])
        Amount = np.random.exponential(scale=100, size=n_samples)
        Time = np.sort(np.random.uniform(0, 172800, size=n_samples))
        Class = np.array([0] * (n_samples - n_fraud) + [1] * n_fraud)
        
        df = pd.DataFrame(V, columns=[f'V{i}' for i in range(1, 29)])
        df['Time'] = Time
        df['Amount'] = Amount
        df['Class'] = Class
        df.to_csv(file_path, index=False)
        print(f"Saved mock dataset to {file_path}")

def engineer_features(df):
    df = df.copy()
    df['hour_of_day'] = ((df['Time'] % 86400) / 3600).astype(int)
    df['amount_log'] = np.log1p(df['Amount'])
    df['high_value_flag'] = (df['Amount'] > df['Amount'].quantile(0.95)).astype(int)
    return df

def train_pipeline(data_path="creditcard.csv", model_dir="../models"):
    os.makedirs(model_dir, exist_ok=True)
    create_synthetic_data_if_missing(data_path)
    
    print("1. Loading Data...")
    df = pd.read_csv(data_path)
    
    print("2. Engineering Features...")
    df = engineer_features(df)
    
    # Target and features setup
    X = df.drop(columns=['Class', 'Time'])
    y = df['Class']
    
    print("3. Stratified Train/Val/Test Split...")
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, stratify=y, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=42)
    
    print("4. Scaling Features (Train Fit Only)...")
    scaler = StandardScaler()
    
    # Scale Amount and amount_log features
    scale_cols = ['Amount', 'amount_log']
    X_train[scale_cols] = scaler.fit_transform(X_train[scale_cols])
    X_val[scale_cols] = scaler.transform(X_val[scale_cols])
    X_test[scale_cols] = scaler.transform(X_test[scale_cols])
    
    print("5. Applying SMOTE to Training Set Only...")
    smote = SMOTE(sampling_strategy=1.0, k_neighbors=5, random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    
    print("6. Training XGBoost Classifier...")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=1.0,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="aucpr",
        random_state=42
    )
    
    model.fit(
        X_train_res, y_train_res,
        eval_set=[(X_val, y_val)],
        verbose=False
    )
    
    print("7. Evaluating Model...")
    preds_proba = model.predict_proba(X_test)[:, 1]
    precision, recall, _ = precision_recall_curve(y_test, preds_proba)
    pr_auc_score = auc(recall, precision)
    
    preds_binary = (preds_proba >= 0.5).astype(int)
    f1 = f1_score(y_test, preds_binary)
    
    print(f"--- Final Test Results ---")
    print(f"PR-AUC: {pr_auc_score:.4f}")
    print(f"F1 Score (Threshold 0.5): {f1:.4f}")
    
    print("8. Initializing and Saving SHAP Explainer...")
    explainer = shap.TreeExplainer(model)
    
    # Save artifacts
    joblib.dump(model, os.path.join(model_dir, "xgboost_model.joblib"))
    joblib.dump(scaler, os.path.join(model_dir, "scaler.joblib"))
    joblib.dump(explainer, os.path.join(model_dir, "shap_explainer.joblib"))
    
    print(f"Artifacts successfully saved to {model_dir}/")

if __name__ == "__main__":
    train_pipeline()