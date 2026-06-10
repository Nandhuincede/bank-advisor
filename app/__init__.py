"""
app/__init__.py — Flask application factory.
"""
import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialise database
    from app.db import database
    database.init_db()

    # Register API blueprint
    from app.api.routes import api_bp
    app.register_blueprint(api_bp)

    # Serve the single-page frontend
    from flask import render_template

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
