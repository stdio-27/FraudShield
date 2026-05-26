import xgboost as xgb
import shap
import joblib
import logging
import os
from sklearn.metrics import precision_recall_curve, auc, confusion_matrix, classification_report

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from preprocess import preprocess_data

def train_and_evaluate(data_path: str, models_dir: str):
    """Trains the XGBoost model, evaluates using PR-AUC, and saves artifacts."""
    
    # 1. Preprocess data (loads, splits, scales, and applies SMOTE)
    train_data, val_data, test_data = preprocess_data(data_path, models_dir)
    X_train, y_train = train_data
    X_val, y_val = val_data
    X_test, y_test = test_data
    
    # 2. Model Configuration
    logging.info("Initializing XGBoost classifier...")
    # scale_pos_weight=1.0 because SMOTE already handled the class imbalance
    clf = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.05,
        n_estimators=300,
        scale_pos_weight=1.0,
        eval_metric='aucpr',
        random_state=42
    )
    
    # 3. Model Training
    logging.info("Training XGBoost model...")
    clf.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=50
    )
    
    # 4. Evaluation (PR-AUC)
    logging.info("\n=== Evaluating Model ===")
    
    # Validation Evaluation
    val_preds_proba = clf.predict_proba(X_val)[:, 1]
    precision_val, recall_val, _ = precision_recall_curve(y_val, val_preds_proba)
    pr_auc_val = auc(recall_val, precision_val)
    logging.info(f"Validation PR-AUC: {pr_auc_val:.4f}")
    
    # Test Evaluation
    test_preds_proba = clf.predict_proba(X_test)[:, 1]
    test_preds = clf.predict(X_test)
    precision_test, recall_test, _ = precision_recall_curve(y_test, test_preds_proba)
    pr_auc_test = auc(recall_test, precision_test)
    logging.info(f"Test PR-AUC:       {pr_auc_test:.4f}")
    
    logging.info("\n--- Test Set Confusion Matrix ---")
    logging.info("\n" + str(confusion_matrix(y_test, test_preds)))
    
    logging.info("\n--- Test Set Classification Report ---")
    logging.info("\n" + classification_report(y_test, test_preds))
    
    # 5. Explainability & Artifact Saving
    os.makedirs(models_dir, exist_ok=True)
    
    # Save Model
    model_path = os.path.join(models_dir, "xgboost_fraud_model.json")
    clf.save_model(model_path)
    logging.info(f"Saved XGBoost model to {model_path}")
    
    # Train and Save SHAP Explainer
    logging.info("Fitting SHAP TreeExplainer...")
    # TreeExplainer is fast and optimized for tree-based models like XGBoost
    explainer = shap.TreeExplainer(clf)
    
    explainer_path = os.path.join(models_dir, "shap_explainer.pkl")
    joblib.dump(explainer, explainer_path)
    logging.info(f"Saved SHAP Explainer to {explainer_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_path = os.path.join(base_dir, "data", "creditcard.csv")
    models_dir = os.path.join(base_dir, "models")
    
    if not os.path.exists(data_path):
        logging.error(f"Dataset not found at {data_path}. Please download creditcard.csv from Kaggle and place it in the data/ directory.")
    else:
        train_and_evaluate(data_path, models_dir)
