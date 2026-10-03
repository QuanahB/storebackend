"""Sign-up and sign-in for the MockMSPaint account screens."""

import re

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User
from serializers import user_to_dict

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.post("/auth/sign-up")
def sign_up():
    """
    POST /auth/sign-up

    Body matches the sign-up form: { "name", "email", "password" }.
    Password must be at least 8 characters, same rule as the form.
    """
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")

    if not name or not email or not password:
        return jsonify(message="Name, email, and password are required."), 400
    if not EMAIL_RE.match(email):
        return jsonify(message="Enter a valid email."), 400
    if len(password) < 8:
        return jsonify(message="Use a password with at least 8 characters."), 400
    if User.query.filter_by(email=email).first() is not None:
        return jsonify(message="An account with that email already exists."), 409

    user = User(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    _login(user)
    return jsonify(user=user_to_dict(user)), 201


@auth_bp.post("/auth/sign-in")
def sign_in():
    """POST /auth/sign-in — body { "email", "password" }."""
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    if not email or not password:
        return jsonify(message="Enter your email and password."), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify(message="Email or password is incorrect."), 401

    _login(user)
    return jsonify(user=user_to_dict(user))


@auth_bp.post("/auth/sign-out")
def sign_out():
    """POST /auth/sign-out — keeps the cart cookie, drops the account."""
    session.pop("user_id", None)
    return jsonify(message="Signed out")


@auth_bp.get("/auth/me")
def me():
    """GET /auth/me — the signed-in shopper, or 401."""
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        return jsonify(message="Not signed in"), 401
    return jsonify(user=user_to_dict(user))


def _login(user: User) -> None:
    session["user_id"] = user.id
    session.permanent = True
