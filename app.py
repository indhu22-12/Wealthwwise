from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Budget, Expense
import os, random, joblib, numpy as np, csv, requests
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

app = Flask(__name__)
app.secret_key = "super_secret_key"

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "budget_tracker.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mobile = request.form["mobile"]
        user = User.query.filter_by(mobile=mobile).first()
        if not user:
            user = User(mobile=mobile, otp="0000")
            db.session.add(user)
            db.session.commit()

        api_key = os.getenv("TWOFACTOR_API_KEY")
        send_url = f"https://2factor.in/API/V1/{api_key}/SMS/{mobile}/AUTOGEN"
        response = requests.get(send_url)
        data = response.json()

        session["mobile"] = mobile
        session["session_id"] = data["Details"]
        return redirect(url_for("verify_otp"))
    return render_template("login.html")

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    mobile = session.get("mobile")
    session_id = session.get("session_id")

    if request.method == "POST":
        entered_otp = request.form["otp"]
        api_key = os.getenv("TWOFACTOR_API_KEY")
        verify_url = f"https://2factor.in/API/V1/{api_key}/SMS/VERIFY/{session_id}/{entered_otp}"
        result = requests.get(verify_url).json()

        if result["Details"] == "OTP Matched":
            user = User.query.filter_by(mobile=mobile).first()
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return "OTP Invalid. Please try again."
    return render_template("verify_otp.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    budget = Budget.query.filter_by(user_id=current_user.id).first()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    categories = list(set(e.category for e in expenses))
    amounts = [sum(e.amount for e in expenses if e.category == cat) for cat in categories]

    advice = ""
    show_celebration = False
    if budget:
        model = joblib.load("ml_model/budget_predictor.pkl")
        total_spent = sum(e.amount for e in expenses)
        X_input = np.array([[budget.monthly_income, budget.savings_goal + total_spent, total_spent]])
        prediction = model.predict(X_input)[0]
        advice = "⚠️ AI Alert: You're about to overspend!" if prediction == 1 else "✅ Great job! You're staying within your budget."

        # Show success only once per achievement
        if total_spent <= (budget.monthly_income - budget.savings_goal):
            if not session.get("goal_achieved_shown"):
                show_celebration = True
                session["goal_achieved_shown"] = True
        else:
            session["goal_achieved_shown"] = False

    return render_template("dashboard.html",
        budget=budget, expenses=expenses,
        categories=categories, amounts=amounts,
        advice=advice, show_celebration=show_celebration
    )

@app.route("/set_budget", methods=["POST"])
@login_required
def set_budget():
    income = float(request.form["income"])
    goal = float(request.form["goal"])
    budget = Budget.query.filter_by(user_id=current_user.id).first()
    if budget:
        budget.monthly_income = income
        budget.savings_goal = goal
    else:
        budget = Budget(user_id=current_user.id, monthly_income=income, savings_goal=goal)
        db.session.add(budget)
    db.session.commit()
    session["goal_achieved_shown"] = False
    return redirect(url_for("dashboard"))

@app.route("/reset_budget")
@login_required
def reset_budget():
    user_id = current_user.id
    Budget.query.filter_by(user_id=user_id).delete()
    Expense.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    session["goal_achieved_shown"] = False
    return redirect(url_for("dashboard"))

@app.route("/add_expense", methods=["POST"])
@login_required
def add_expense():
    data = request.get_json()
    category = data["category"]
    item = data["item"]
    amount = float(data["amount"])
    date = datetime.now().strftime("%Y-%m-%d")

    new_expense = Expense(user_id=current_user.id, category=category, item=item, amount=amount, date=date)
    db.session.add(new_expense)
    db.session.commit()

    budget = Budget.query.filter_by(user_id=current_user.id).first()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    total_spent = sum(e.amount for e in expenses)

    goal_alert = ""
    advice = ""
    previous_spent = total_spent - amount
    threshold = budget.monthly_income - budget.savings_goal

    category_advice = {
        "GROCERY": "🛒 Try sticking to a weekly essentials list.",
        "ENTERTAINMENT": "🎮 Cut down on subscriptions or game spending.",
        "DINING & SOCIAL LIFE": "🍕 Choose home-cooked over dining out.",
        "TRAVEL & TRANSPORT": "🚇 Opt for public transport or carpooling.",
        "HOME NEEDS": "🏠 Reduce electricity & maintenance where possible.",
        "LIFESTYLE & WELLNESS": "🧘 Skip luxury brands and go minimal."
    }

    if budget and previous_spent < threshold <= total_spent:
        goal_alert = ""

    elif budget and total_spent > threshold:
        advice = category_advice.get(category, "💡 Re-evaluate your expenses in this category.")
        goal_alert = f"🚨 Overspending Alert!\nYou've exceeded your savings goal.\nCategory: {category}\nAdvice: {advice}"
        user = User.query.get(current_user.id)
        msg = f"WealthWise ⚠️ ALERT:\nExpense ₹{amount} on {item} in {category} exceeded your savings goal.\nAdvice: {advice}"
        api_key = os.getenv("TWOFACTOR_API_KEY")
        sms_url = f"https://2factor.in/API/V1/{api_key}/ADDON_SERVICES/SEND/TSMS"
        requests.post(sms_url, json={"From": "WEALTHW", "To": user.mobile, "Msg": msg})

    return jsonify({
        "message": f"✅ {item} added under {category}!",
        "goal_alert": goal_alert
    })

@app.route("/download_csv")
@login_required
def download_csv():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    si = [["Category", "Item", "Amount", "Date"]]
    for e in expenses:
        si.append([e.category, e.item, e.amount, e.date])

    def generate():
        for row in si:
            yield ",".join(map(str, row)) + "\n"

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expenses.csv"})

@app.route("/analytics")
@login_required
def analytics():
    user = current_user
    budget = Budget.query.filter_by(user_id=user.id).first()
    if not budget:
        return redirect(url_for('dashboard'))

    expenses = Expense.query.filter_by(user_id=user.id).all()

    by_category = defaultdict(float)
    by_date = defaultdict(float)
    for e in expenses:
        by_category[e.category] += e.amount
        by_date[e.date] += e.amount

    total_spent = sum(e.amount for e in expenses)
    savings_data = [
        budget.savings_goal,
        max(0, budget.monthly_income - total_spent - budget.savings_goal)
    ]

    return render_template("analytics.html",
        categories=list(by_category.keys()),
        amounts=list(by_category.values()),
        savings=savings_data,
        by_date=by_date,
        by_category=by_category
    )

@app.route("/summary_data")
@login_required
def summary_data():
    budget = Budget.query.filter_by(user_id=current_user.id).first()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    total_spent = sum(e.amount for e in expenses)

    tip = ""
    if budget:
        available = budget.monthly_income - total_spent
        if total_spent > (budget.monthly_income - budget.savings_goal):
            shortage = total_spent - (budget.monthly_income - budget.savings_goal)
            tip = f"⚠️ Exceeded your goal! Save at least ₹{shortage:.2f} more to get back on track."
        else:
            tip = f"✅ You can still spend ₹{available - budget.savings_goal:.2f} and meet your savings goal."

    return jsonify({
        "total": total_spent,
        "income": budget.monthly_income,
        "goal": budget.savings_goal,
        "tip": tip
    })

if __name__ == "__main__":
    app.run(debug=True)
