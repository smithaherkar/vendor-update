import joblib
from pathlib import Path
from data_preprocessing import load_invoice_vendor_data,prepare_feature,split_dataset
from model_evaluation import train_linear_regressor,train_decision_tree,train_random_forest_regressor,evaluate_model

def main():
    db_path="D:/vendor intelligence/data/inventory.db"
    model_dir=Path("models")
    model_dir.mkdir(exist_ok=True)

    #load data
    df=load_invoice_vendor_data(db_path)

    #prepare feature 
    X,y=prepare_feature(df)
    X_train, X_test, y_train, y_test = split_dataset(X, y)

    lr = train_linear_regressor(X_train, y_train)
    dt = train_decision_tree(X_train, y_train)
    rf = train_random_forest_regressor(X_train, y_train)

    result = []

    result.append(evaluate_model(lr, X_test, y_test, "Linear Regression"))
    result.append(evaluate_model(dt, X_test, y_test, "Decision Tree Regression"))
    result.append(evaluate_model(rf, X_test, y_test, "Random Forest Regression"))

    best_model_info = min(result, key=lambda x: x["mean_absolute"])
    best_model_name = best_model_info["model_name"]

    best_model = {
        "Linear Regression": lr,
        "Decision Tree Regression": dt,
        "Random Forest Regression": rf
    }[best_model_name]
    
    # Save best model
    model_path = model_dir / "predict_freight_model.pkl"
    joblib.dump(best_model, model_path)
    
    print(f"\nBest model saved: {best_model_name}")
    print(f"Model path: {model_path}")
    
if __name__ == "__main__":
    main()
    
