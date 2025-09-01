
from flask import Flask, render_template, session, request, jsonify
from flask import redirect, url_for
from datetime import timedelta
from blueprints.auth import auth_bp
from blueprints.chat import chat_bp
from blueprints.sundalex import sundalex_bp

def create_app():
    app = Flask(__name__)
    # ⚠️ Ganti dengan kunci rahasia Anda
    app.config["SECRET_KEY"] = "8c2f4a8dd91d42e4b6db6d67a0efda2d6a6f6b49d64cddbe7a6ab58d2b7cd2fe"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(sundalex_bp)

    @app.route("/")
    def index():
        # Redirect ke chat jika sudah login, kalau belum ke /login
        if session.get("user"):
            return render_template("chat.html")
        return redirect(url_for("auth.login_view"))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
