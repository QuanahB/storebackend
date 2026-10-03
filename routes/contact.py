"""Contact form inbox."""

import re

from flask import Blueprint, jsonify, request

from extensions import db
from models import ContactMessage

contact_bp = Blueprint("contact", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@contact_bp.post("/contact")
def create_message():
    """
    POST /contact

    Body matches the contact form: { "name", "email", "message" }.
    """
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    message = str(body.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify(message="Fill in your name, email, and message."), 400
    if len(name) > 120:
        return jsonify(message="Name is too long."), 400
    if not EMAIL_RE.match(email):
        return jsonify(message="Enter a valid email."), 400
    if len(message) > 5000:
        return jsonify(message="Message is too long."), 400

    note = ContactMessage(name=name, email=email, message=message)
    db.session.add(note)
    db.session.commit()
    return jsonify(message="Message received.", id=note.id), 201
