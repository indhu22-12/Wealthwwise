import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import joblib

# Sample dataset (Total Expenses vs Budget)
data = {
    "total_spent": [500, 800, 1200, 1500, 2000, 2500, 3000],
    "budget": [1000, 1000, 1000, 2000, 2000, 2000, 3000],
    "over_budget": [0, 0, 1, 0, 1, 1, 1]  # 1 means overspent
}

df = pd.DataFrame(data)
X = df[["total_spent", "budget"]]
y = df["over_budget"]

model = LinearRegression()
model.fit(X, y)

joblib.dump(model, "budget_predictor.pkl")

