from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    otp = db.Column(db.String(10))

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    monthly_income = db.Column(db.Float)
    savings_goal = db.Column(db.Float)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    category = db.Column(db.String(100))
    item = db.Column(db.String(100))
    amount = db.Column(db.Float)
    date = db.Column(db.String(20))
