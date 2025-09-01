
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from supabase_flask import login, register, logout

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login_view():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        ok = login(email, password)
        if ok.get("ok"):
            return redirect(url_for("chat.chat_view"))
        flash(ok.get("error", "Login gagal"), "danger")
    return render_template("login.html", title="Login")

@auth_bp.route("/register", methods=["GET", "POST"])
def register_view():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        age = request.form.get("age", "25")
        ok = register(email, password, int(age))
        if not ok.get("ok"):
            flash(ok.get("error", "Registrasi gagal"), "danger")
            return render_template("register.html")
        flash("Registrasi berhasil. Silakan login.", "success")
        return redirect(url_for("auth.login_view"))
    return render_template("register.html", title="Register")

@auth_bp.route("/logout")
def logout_view():
    logout()
    return redirect(url_for("auth.login_view"))
