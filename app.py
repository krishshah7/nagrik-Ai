"""
app.py
Nagrik AI 2.0 - Flask entry point.
Run with:  python app.py
Default admin login: admin@nagrik.ai / admin123  (change this after first login in real use)
"""

import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from dotenv import load_dotenv

from models import db, User, Complaint
import ai_agents

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-this")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nagrik.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


WARDS = ["Ward 1", "Ward 2", "Ward 3", "Ward 4", "Ward 5"]
CATEGORIES = ["Road Damage", "Drainage", "Garbage", "Streetlight", "Water Supply", "Illegal Construction", "Other"]
STATUSES = ["Pending", "In Progress", "Resolved"]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("admin_panel") if current_user.is_admin else url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.")
            return redirect(url_for("register"))

        user = User(name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("admin_panel") if user.is_admin else url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Complaints (CRUD)
# ---------------------------------------------------------------------------

@app.route("/submit", methods=["GET", "POST"])
@login_required
def submit_complaint():
    if request.method == "POST":
        description = request.form["description"].strip()
        ward = request.form["ward"]

        ai_result = ai_agents.classify_complaint(description)

        complaint = Complaint(
            user_id=current_user.id,
            description=description,
            ward=ward,
            category=ai_result.get("category", "Other"),
            severity=ai_result.get("severity", "Medium"),
            summary=ai_result.get("summary", description[:150]),
            suggested_action=ai_result.get("suggested_action", ""),
            status="Pending",
        )
        db.session.add(complaint)
        db.session.commit()
        flash("Complaint submitted successfully.")
        return redirect(url_for("dashboard"))

    return render_template("submit.html", wards=WARDS)


@app.route("/api/rewrite", methods=["POST"])
@login_required
def api_rewrite():
    text = request.json.get("text", "")
    return jsonify({"rewritten": ai_agents.rewrite_complaint(text)})


@app.route("/dashboard")
@login_required
def dashboard():
    query = Complaint.query if current_user.is_admin else Complaint.query.filter_by(user_id=current_user.id)

    search = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    status = request.args.get("status", "")

    if search:
        query = query.filter(Complaint.description.ilike(f"%{search}%"))
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)

    complaints = query.order_by(Complaint.created_at.desc()).all()
    return render_template(
        "dashboard.html",
        complaints=complaints,
        categories=CATEGORIES,
        statuses=STATUSES,
        search=search,
        category=category,
        status=status,
    )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash("Access denied - admin only.")
        return redirect(url_for("dashboard"))

    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template("admin.html", complaints=complaints, statuses=STATUSES)


@app.route("/complaint/<int:complaint_id>/status", methods=["POST"])
@login_required
def update_status(complaint_id):
    if not current_user.is_admin:
        flash("Access denied - admin only.")
        return redirect(url_for("dashboard"))

    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.status = request.form["status"]
    db.session.commit()
    flash(f"Complaint #{complaint.id} marked as {complaint.status}.")
    return redirect(url_for("admin_panel"))


# ---------------------------------------------------------------------------
# AI Assistant (Phase 2 guidance + Phase 3 RAG + Phase 4 agent routing)
# ---------------------------------------------------------------------------

@app.route("/assistant")
@login_required
def assistant():
    return render_template("assistant.html")


def _get_stats():
    ward_counts = dict(db.session.query(Complaint.ward, func.count(Complaint.id)).group_by(Complaint.ward).all())
    category_counts = dict(
        db.session.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    )
    status_counts = dict(
        db.session.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()
    )
    return {
        "ward_counts": ward_counts,
        "category_counts": category_counts,
        "status_counts": status_counts,
        "total_complaints": Complaint.query.count(),
    }


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    message = request.json.get("message", "")
    stats = _get_stats()
    answer = ai_agents.run_agent(message, stats)
    return jsonify({"answer": answer})


# ---------------------------------------------------------------------------
# DB setup + default admin
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="admin@nagrik.ai").first():
        db.session.add(
            User(
                name="Admin",
                email="admin@nagrik.ai",
                password_hash=generate_password_hash("admin123"),
                is_admin=True,
            )
        )
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)
