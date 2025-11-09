import pandas as pd
import numpy as np
import re
import datetime
import joblib
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    accuracy_score, f1_score, classification_report, confusion_matrix
)

# ---------- CONFIG ----------
excel_path = "codechef_START202D_contest_data.xlsx"  # change if needed
random_state = 42
min_problems_threshold = 4  # classifier threshold
# ----------------------------

def safe_extract_number(s):
    """Extract numeric part of a string safely."""
    if pd.isnull(s): return np.nan
    s = str(s)
    m = re.search(r"[-+]?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else np.nan

def parse_last_ac_to_days(s):
    """Convert 'Last AC' text into days difference."""
    if pd.isnull(s) or str(s).strip() in ["N/A", "-"]: return -1
    s = str(s)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%b %d, %Y", "%d %b %Y"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return (datetime.datetime.now() - dt).days
        except: pass
    if "day" in s:
        m = re.search(r"(\d+)\s+day", s)
        if m: return int(m.group(1))
    if "hour" in s: return 0
    return -1

def load_and_preprocess(path):
    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [c.strip() for c in df.columns]
    print(f"Detected columns: {list(df.columns)}")

    # Identify problem columns (P1..P8)
    problem_cols = [c for c in df.columns if re.match(r"^P\d+$", c.strip(), re.I)]
    if not problem_cols:
        problem_cols = [c for c in df.columns if "P" in c and any(ch.isdigit() for ch in c)]

    # Parse problem scores
    for pc in problem_cols:
        df[pc + "_score"] = df[pc].fillna("-").map(lambda x: safe_extract_number(x) if str(x).strip() != "-" else 0.0)

    # Parse Rank
    def parse_rank(x):
        if pd.isnull(x): return np.nan
        m = re.search(r"\d+", str(x))
        return int(m.group(0)) if m else np.nan

    rank_col = next((c for c in df.columns if "rank" in c.lower()), None)
    if rank_col:
        df["Rank_num"] = df[rank_col].map(parse_rank)
    else:
        df["Rank_num"] = np.arange(1, len(df) + 1)  # fallback fake rank if missing

    # Parse Total Score
    total_col = next((c for c in df.columns if "total" in c.lower() and "score" in c.lower()), None)
    if total_col:
        df["TotalScore_num"] = df[total_col].map(safe_extract_number)
    else:
        df["TotalScore_num"] = df[[pc + "_score" for pc in problem_cols]].sum(axis=1)

    # Parse Problems Solved
    if "Problems Solved" in df.columns:
        df["Problems Solved"] = df["Problems Solved"].fillna(0).astype(int)
    else:
        df["Problems Solved"] = df[[pc + "_score" for pc in problem_cols]].apply(lambda r: (r > 0).sum(), axis=1)

    # Parse Last AC
    last_ac_col = next((c for c in df.columns if "last" in c.lower() and "ac" in c.lower()), None)
    if last_ac_col:
        df["LastAC_days"] = df[last_ac_col].map(parse_last_ac_to_days)
    else:
        df["LastAC_days"] = -1

    # Add engineered features
    score_cols = [pc + "_score" for pc in problem_cols]
    df["num_attempted"] = df[score_cols].apply(lambda r: int((r > 0).sum()), axis=1)
    df["avg_problem_score"] = df[score_cols].mean(axis=1)
    df["max_problem_score"] = df[score_cols].max(axis=1)
    df["std_problem_score"] = df[score_cols].std(axis=1).fillna(0)

    # Clean
    df = df.fillna(-1)
    df.to_csv("processed_features.csv", index=False)
    print("✅ Processed features saved to processed_features.csv")
    return df, problem_cols

def build_and_evaluate_models(df):
    if "Rank_num" not in df.columns or "Problems Solved" not in df.columns:
        raise ValueError("Missing 'Rank_num' or 'Problems Solved' columns after preprocessing!")

    features = ["num_attempted", "avg_problem_score", "max_problem_score", "std_problem_score", "LastAC_days"]
    X = df[features].values
    y_rank = df["Rank_num"].astype(float).values
    y_class = (df["Problems Solved"] >= min_problems_threshold).astype(int)

    X_train, X_test, y_rank_train, y_rank_test, y_class_train, y_class_test = train_test_split(
        X, y_rank, y_class, test_size=0.2, random_state=random_state
    )

    # --- Rank Regressor ---
    reg = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestRegressor(random_state=random_state))
    ])
    reg.fit(X_train, y_rank_train)
    y_pred = reg.predict(X_test)
    print("\n=== Rank Regressor ===")
    print("MAE:", mean_absolute_error(y_rank_test, y_pred))
    print("R2:", r2_score(y_rank_test, y_pred))

    # --- Classifier ---
    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(random_state=random_state))
    ])
    clf.fit(X_train, y_class_train)
    y_cpred = clf.predict(X_test)
    print("\n=== Problem Solved Classifier ===")
    print("Accuracy:", accuracy_score(y_class_test, y_cpred))
    print("F1:", f1_score(y_class_test, y_cpred))
    print("Confusion Matrix:\n", confusion_matrix(y_class_test, y_cpred))

    joblib.dump(reg, "rank_regressor.joblib")
    joblib.dump(clf, "solved_classifier.joblib")
    print("\n💾 Models saved: rank_regressor.joblib, solved_classifier.joblib")

    return reg, clf, features

def predict_sample(reg_model, clf_model, features, sample):
    Xs = np.array([[sample[f] for f in features]])
    rank_pred = reg_model.predict(Xs)[0]
    class_pred = clf_model.predict(Xs)[0]
    print("\n🧩 Prediction Demo:")
    print("Predicted Rank:", rank_pred)
    print(f"Predicted '≥{min_problems_threshold} solved' →", "YES" if class_pred else "NO")
    return rank_pred, class_pred

if __name__ == "__main__":
    print("Loading and preprocessing data...")
    df, problem_cols = load_and_preprocess(excel_path)
    reg_model, clf_model, feature_list = build_and_evaluate_models(df)

    # Demo Prediction
    demo_sample = df[feature_list].mean().to_dict()
    print("\n--- Demo Sample ---")
    print(demo_sample)
    predict_sample(reg_model, clf_model, feature_list, demo_sample)
