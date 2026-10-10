"""Public anonymous notes for the Paint status bar."""

import time

from flask import Blueprint, jsonify, request, session

from extensions import db
from models import BoardNote
from serializers import isoformat

board_bp = Blueprint("board", __name__)

MAX_LENGTH = 240
COOLDOWN_SECONDS = 30
LIST_LIMIT = 40


@board_bp.get("/board")
def list_notes():
    """GET /board — newest notes first. No names are stored."""
    notes = BoardNote.query.order_by(BoardNote.id.desc()).limit(LIST_LIMIT).all()
    return jsonify([_note_to_dict(note) for note in notes])


@board_bp.post("/board")
def create_note():
    """
    POST /board

    Body: { "message" }. One note per browser every 30 seconds.
    """
    body = request.get_json(silent=True) or {}
    message = " ".join(str(body.get("message") or "").split())
    if not message:
        return jsonify(message="Write a note first."), 400
    if len(message) > MAX_LENGTH:
        return jsonify(message=f"Notes are limited to {MAX_LENGTH} characters."), 400

    now = time.time()
    last_post = session.get("board_last_post")
    if isinstance(last_post, (int, float)) and now - float(last_post) < COOLDOWN_SECONDS:
        return jsonify(message="Wait a moment before posting again."), 429

    note = BoardNote(message=message)
    db.session.add(note)
    db.session.commit()
    session["board_last_post"] = now
    session.permanent = True
    return jsonify(_note_to_dict(note)), 201


def _note_to_dict(note: BoardNote) -> dict:
    return {
        "id": note.id,
        "message": note.message,
        "created_at": isoformat(note.created_at),
    }
