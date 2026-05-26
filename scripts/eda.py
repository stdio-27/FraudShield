import pandas as pd
import os

def run_eda(filepath: str):
    print(f"Loading dataset from {filepath}...")
    if not os.path.exists(filepath):
        print(f"Error: Dataset not found at {filepath}")
        print("Please download 'creditcard.csv' from Kaggle and place it in the data/ directory.")
        return

    df = pd.read_csv(filepath)
    
    print("\n--- Basic Statistics ---")
    print(f"Total rows: {len(df)}")
    print(f"Total columns: {len(df.columns)}")
    
    print("\n--- Missing Values ---")
    missing = df.isnull().sum().sum()
    print(f"Total missing values: {missing}")

    print("\n--- Class Distribution ---")
    if 'Class' in df.columns:
        class_counts = df['Class'].value_counts()
        total = len(df)
        normal_pct = (class_counts.get(0, 0) / total) * 100
        fraud_pct = (class_counts.get(1, 0) / total) * 100
        
        print(f"Normal (0): {class_counts.get(0, 0)} ({normal_pct:.2f}%)")
        print(f"Fraud (1): {class_counts.get(1, 0)} ({fraud_pct:.2f}%)")
        
        if round(fraud_pct, 2) == 0.17:
            print("\n[INFO] Class imbalance matches expected 99.83% / 0.17% distribution.")
        else:
            print("\n[WARNING] Class imbalance does not match the expected 99.83% / 0.17%.")
    else:
        print("Error: 'Class' column not found in dataset.")

if __name__ == "__main__":
    dataset_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'creditcard.csv')
    run_eda(dataset_path)
