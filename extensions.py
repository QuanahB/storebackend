"""Shared Flask extensions, kept separate so models can import db safely."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
