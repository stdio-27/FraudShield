import os
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import PrecisionRecallDisplay, confusion_matrix, ConfusionMatrixDisplay
import shap

# Create directory for report figures
output_dir = "../../report_images"
os.makedirs(output_dir, exist_ok=True)

# 1. Class Distribution Pie Chart
plt.figure(figsize=(6, 6))
labels = ['Genuine (99.83%)', 'Fraud (0.17%)']
sizes = [284315, 492]
colors = ['#2ecc71', '#e74c3c']
plt.pie(sizes, labels=labels, autopct='%1.2f%%', colors=colors, startangle=140, explode=(0, 0.1))
plt.title('Kaggle Credit Card Dataset Class Distribution')
plt.savefig(os.path.join(output_dir, 'class_distribution_pie.png'), dpi=300, bbox_inches='tight')
plt.close()

# Load saved model & test data to generate performance plots
model = joblib.load("../models/xgboost_model.joblib")
explainer = joblib.load("../models/shap_explainer.joblib")

# Load a sample test set (or mock test data)
from train import create_synthetic_data_if_missing, engineer_features
create_synthetic_data_if_missing("creditcard.csv")
df = engineer_features(pd.read_csv("creditcard.csv"))
X = df.drop(columns=['Class', 'Time'])
y = df['Class']

# 2. Confusion Matrix Heatmap
cm = confusion_matrix(y, model.predict(X))
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=['Genuine', 'Fraud'])
disp.plot(cmap='Blues')
plt.title('FraudShield XGBoost Confusion Matrix')
plt.savefig(os.path.join(output_dir, 'confusion_matrix.png'), dpi=300, bbox_inches='tight')
plt.close()

# 3. Precision-Recall Curve
PrecisionRecallDisplay.from_estimator(model, X, y)
plt.title('Precision-Recall Curve (PR-AUC)')
plt.savefig(os.path.join(output_dir, 'pr_auc_curve.png'), dpi=300, bbox_inches='tight')
plt.close()

# 4. Global SHAP Summary Plot
plt.figure()
shap_values = explainer.shap_values(X.iloc[:100])
shap.summary_plot(shap_values, X.iloc[:100], show=False)
plt.savefig(os.path.join(output_dir, 'shap_summary_plot.png'), dpi=300, bbox_inches='tight')
plt.close()

print(f"All plots successfully generated in: {os.path.abspath(output_dir)}")