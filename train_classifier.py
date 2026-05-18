"""
Query Classifier Training Script
================================
Scans for CSV files, merges them, processes query/category pairs, 
validates performance, and saves a trained Logistic Regression model 
to the active backend path. Emojis removed to prevent Windows console encoding issues.
"""
import os
import glob
import pickle
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

# Active model path
MODEL_DIR = os.path.join(os.path.dirname(__file__), "Backend", "ml")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")

def scan_and_merge_csvs(data_directory="./"):
    """Scans data_directory for CSVs and merges query/category pairs."""
    csv_files = glob.glob(os.path.join(data_directory, "*.csv"))
    # Also scan in Data folder if exists
    data_folder = os.path.join(data_directory, "Data")
    if os.path.isdir(data_folder):
        csv_files.extend(glob.glob(os.path.join(data_folder, "*.csv")))

    if not csv_files:
        print("[ERROR] No CSV files found in the current directory or Data/ folder!")
        return None

    print(f"[SEARCH] Found {len(csv_files)} CSV files: {', '.join([os.path.basename(f) for f in csv_files])}")
    
    all_dfs = []
    
    for file in csv_files:
        try:
            # Auto-detect if CSV is headerless (exactly 2 columns and no matching keywords)
            temp_df = pd.read_csv(file, nrows=2)
            has_header = False
            for col in temp_df.columns:
                if str(col).lower().strip() in ["query", "question", "text", "queries", "category", "label", "class", "type"]:
                    has_header = True
                    break
            
            if not has_header and len(temp_df.columns) == 2:
                df = pd.read_csv(file, header=None, names=["query", "category"])
            else:
                df = pd.read_csv(file)
                
            # Normalize column names to lowercase
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            # Map query/text column
            query_col = None
            for opt in ["query", "question", "text", "queries"]:
                if opt in df.columns:
                    query_col = opt
                    break
            
            # Map category/label column
            cat_col = None
            for opt in ["category", "label", "class", "type"]:
                if opt in df.columns:
                    cat_col = opt
                    break
            
            if query_col and cat_col:
                sliced = df[[query_col, cat_col]].copy()
                sliced.columns = ["query", "category"]
                all_dfs.append(sliced)
                print(f"  [LOADED] {len(sliced)} rows from {os.path.basename(file)}")
            else:
                print(f"  [SKIPPED] {os.path.basename(file)}: Could not map columns (needs 'query'/'question' and 'category'/'label'). Columns found: {df.columns.tolist()}")
        except Exception as e:
            print(f"  [ERROR] Error reading {os.path.basename(file)}: {e}")

    if not all_dfs:
        return None

    merged = pd.concat(all_dfs, ignore_index=True)
    return merged

def clean_data(df):
    """Clean dataset."""
    initial_rows = len(df)
    # Drop rows with null values
    df = df.dropna(subset=["query", "category"])
    
    # Strip spaces
    df["query"] = df["query"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip().str.lower()
    
    # Drop empty strings
    df = df[df["query"] != ""]
    df = df[df["category"] != ""]
    
    # Drop duplicate queries
    df = df.drop_duplicates(subset=["query"])
    
    print(f"[CLEAN] Kept {len(df)} unique rows out of {initial_rows} raw records.")
    return df

def main():
    print("=" * 60)
    print("        AI KNOWLEDGE ASSISTANT - QUERY CLASSIFIER TRAINER")
    print("=" * 60)

    # 1. Scan and Load Data
    df = scan_and_merge_csvs()
    if df is None:
        print("[ERROR] Training failed: No valid training data found.")
        return

    # 2. Preprocess Data
    df = clean_data(df)
    
    if len(df) < 15:
        print("[ERROR] Dataset is too small to train reliably. Please add more rows.")
        return

    texts = df["query"].tolist()
    labels = df["category"].tolist()

    # 3. Print Category Distribution
    print("\n[DATASET] Category Distribution:")
    dist = df["category"].value_counts()
    for cat, count in dist.items():
        print(f"  • {cat:<18}: {count} queries ({count/len(df)*100:.1f}%)")

    # 4. Train-Test Split for Validation
    print("\n[EVALUATE] Evaluating classifier on 20% test subset...")
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    # 5. Define ML Pipeline
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2), 
            min_df=2, 
            max_features=10000, 
            sublinear_tf=True
        )),
        ("clf", LogisticRegression(
            max_iter=2000, 
            C=4.0, 
            solver="lbfgs",
            class_weight="balanced"  # Handles class imbalances elegantly
        ))
    ])

    # Fit validation model
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"[ACCURACY] Model Accuracy on Validation Subset: {accuracy * 100:.2f}%")
    print("\n[REPORT] Detailed Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    # 6. Train on Full Dataset
    print("[TRAIN] Training final model on 100% of data...")
    final_pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=10000, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced"))
    ])
    final_pipeline.fit(texts, labels)

    # 7. Save Model
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(final_pipeline, f)
        
    print("=" * 60)
    print(f"[SUCCESS] Model saved successfully to {MODEL_PATH}")
    print("=" * 60)

if __name__ == "__main__":
    main()
