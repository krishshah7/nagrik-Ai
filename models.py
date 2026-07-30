"""
models.py
Database models for Nagrik AI (Phase 1 - SQLite via SQLAlchemy).
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    complaints = db.relationship("Complaint", backref="user", lazy=True)


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    description = db.Column(db.Text, nullable=False)
    ward = db.Column(db.String(50))

    # Filled in automatically by the Complaint Agent (Phase 2)
    category = db.Column(db.String(50), default="Other")
    severity = db.Column(db.String(20), default="Medium")
    summary = db.Column(db.Text)
    suggested_action = db.Column(db.Text)

    status = db.Column(db.String(20), default="Pending")  # Pending / In Progress / Resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
