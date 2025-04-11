import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

data = {
    "Income": [2000, 1800, 2500, 2200, 3000],
    "Budget": [1000, 1200, 1500, 1300, 2000],
    "Expense": [900, 1300, 1400, 1200, 2100],
    "Exceeded_Budget": [0, 1, 0, 0, 1]
}

df = pd.DataFrame(data)
X = df[['Income', 'Budget', 'Expense']]
y = df['Exceeded_Budget']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

joblib.dump(model, "ml_model/budget_predictor.pkl")
print("Model trained and saved successfully!")
