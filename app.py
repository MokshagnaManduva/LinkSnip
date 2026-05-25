"""
app.py - Flask application for the URL Shortener
==================================================
Routes:
  GET  /                  → Landing / home page
  POST /shorten           → Create a short URL (JSON or form data)
  GET  /<short_id>        → Redirect to original URL (302)
  GET  /stats             → Dashboard with all links sorted by clicks
  GET  /api/stats/<id>    → JSON analytics for a single link
"""

import os

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
)

from db import URL, get_db, shutdown_session
from utils import generate_short_id, sanitize_alias, truncate_url, validate_url

# ---------------------------------------------------------------------------
# Load environment variables from .env (no-op if file is missing)
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Flask app factory-style initialization
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key")

# The public base URL used to construct short links.
# Strip trailing slash so we can safely append "/<short_id>".
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000").rstrip("/")

# Register the session cleanup hook so connections return to the pool
# after every request (even if an exception occurred).
app.teardown_appcontext(shutdown_session)

# Make truncate_url available inside Jinja2 templates as a filter.
app.jinja_env.filters["truncate_url"] = truncate_url



# =============================================================================
# Routes
# =============================================================================

@app.route("/")
def index():
    """Render the home / landing page."""
    return render_template("index.html", base_url=BASE_URL)


# ---- URL Shortening --------------------------------------------------------

@app.route("/shorten", methods=["POST"])
def shorten():
    """
    Create a shortened URL.

    Accepts:
      - JSON body:  {"original_url": "...", "custom_alias": "..."}
      - Form data:  original_url=...&custom_alias=...

    Returns JSON:
      201 → {"short_url": "...", "short_id": "..."}
      400 → {"error": "..."}  (validation failure)
      409 → {"error": "..."}  (alias already taken)
    """
    # --- 1. Parse input (support both JSON and form-encoded) ----------------
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    original_url = data.get("original_url", "").strip()
    custom_alias = data.get("custom_alias", "").strip()

    # --- 2. Validate the URL ------------------------------------------------
    is_valid, error_msg = validate_url(original_url)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    session = get_db()

    # --- 3. Determine the short_id ------------------------------------------
    if custom_alias:
        # Validate the custom alias format
        alias_ok, alias_err = sanitize_alias(custom_alias)
        if not alias_ok:
            return jsonify({"error": alias_err}), 400

        # Check for uniqueness
        existing = session.query(URL).filter_by(short_id=custom_alias).first()
        if existing:
            return jsonify({"error": "That alias is already taken."}), 409

        short_id = custom_alias
    else:
        # Generate a random short_id, retrying on the unlikely collision
        short_id = generate_short_id()
        max_attempts = 10
        attempts = 0
        while session.query(URL).filter_by(short_id=short_id).first():
            short_id = generate_short_id()
            attempts += 1
            if attempts >= max_attempts:
                return jsonify({"error": "Unable to generate a unique short ID. Please try again."}), 500

    # --- 4. Persist the new URL mapping -------------------------------------
    new_url = URL(short_id=short_id, original_url=original_url)
    session.add(new_url)

    try:
        session.commit()
    except Exception:
        session.rollback()
        return jsonify({"error": "Database error. Please try again."}), 500

    short_url = f"{BASE_URL}/{short_id}"

    return jsonify({"short_url": short_url, "short_id": short_id}), 201


# ---- Stats Dashboard -------------------------------------------------------

@app.route("/stats")
def stats():
    """
    Render the stats dashboard showing all shortened URLs
    sorted by click count (most popular first).
    """
    session = get_db()
    urls = session.query(URL).order_by(URL.click_count.desc()).all()
    return render_template("stats.html", urls=urls, base_url=BASE_URL)


# ---- API: Single-link analytics -------------------------------------------

@app.route("/api/stats/<short_id>")
def api_stats(short_id: str):
    """
    Return JSON analytics for a single short link.

    Response 200:
      {
        "short_id":     "aB3xZ9",
        "original_url": "https://...",
        "click_count":  42,
        "created_at":   "2026-05-24T10:30:00"
      }

    Response 404:
      {"error": "Short URL not found."}
    """
    session = get_db()
    url_entry = session.query(URL).filter_by(short_id=short_id).first()

    if not url_entry:
        return jsonify({"error": "Short URL not found."}), 404

    return jsonify(url_entry.to_dict()), 200


# ---- URL Redirection (must be LAST — it's a catch-all) --------------------

@app.route("/<short_id>")
def redirect_to_url(short_id: str):
    """
    Look up a short_id, increment its click counter, and 302-redirect
    to the original URL.

    Returns 404 if the short_id doesn't exist.
    """
    session = get_db()
    url_entry = session.query(URL).filter_by(short_id=short_id).first()

    if not url_entry:
        abort(404)

    # Increment click count
    url_entry.click_count += 1

    try:
        session.commit()
    except Exception:
        session.rollback()
        # Still redirect even if the counter update fails — better UX
        pass

    return redirect(url_entry.original_url, code=302)


# =============================================================================
# Custom Error Handlers
# =============================================================================

@app.errorhandler(404)
def not_found(error):
    """Return a JSON error for API consumers or a simple HTML page."""
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"error": "Not found."}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    """Catch unexpected server errors gracefully."""
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"error": "Internal server error."}), 500
    return "Internal Server Error", 500


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    # Only used for local development; production uses gunicorn.
    app.run(debug=True, host="0.0.0.0", port=5000)
