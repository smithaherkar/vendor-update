from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error,root_mean_squared_error,r2_score

def train_linear_regressor(X_train,y_train):
    model1=LinearRegression()
    model1.fit(X_train,y_train)
    return model1

def train_decision_tree(X_train,y_train,max_depth=5,random_state=42):
    model=DecisionTreeRegressor(max_depth=max_depth,random_state=random_state)
    model.fit(X_train,y_train)
    return model

def train_random_forest_regressor(X_train,y_train,max_depth=5,random_state=42):
    model=RandomForestRegressor(max_depth=max_depth,random_state=random_state)
    model.fit(X_train,y_train)
    return model

def evaluate_model(model,X_test,y_test,model_name)->dict:
    pred=model.predict(X_test)

    mae=mean_absolute_error(y_test,pred)
    rmse=root_mean_squared_error(y_test,pred)
    r2=r2_score(y_test,pred)*100

    print(f"\n {model_name} : Performance")
    print(f"MAE : {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"R2: {r2:.2f}%")

    return{
        "model_name":model_name,
        "mean_absolute":mae,
        "root_mean_square":rmse,
        "R2_score":r2        
    }