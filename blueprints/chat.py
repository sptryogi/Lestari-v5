from flask import Blueprint, render_template, request, jsonify, session, Response
from services.chatbot_service import generate_reply, _normalize_settings
from supabase_flask import append_chat, read_history, delete_history
from utils.error_handler import handle_chatbot_errors

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat", methods=["GET"])
def chat_view():
    if not session.get("user"):
        return render_template("login.html")
    return render_template("chat.html")


@chat_bp.route("/chat", methods=["POST"])
@handle_chatbot_errors
def chat_api():
    try:
        data = request.get_json()
        message = data.get("message")

        # update session setting dari request
        if "fitur" in data: 
            session["fitur"] = data["fitur"]
        if "mode_bahasa" in data:
            session["mode_bahasa"] = data["mode_bahasa"]
        if "chat_mode" in data:
            session["chat_mode"] = data["chat_mode"]
        if "tingkat_tutur" in data:
            session["tingkat_tutur"] = data["tingkat_tutur"]
        session.modified = True

        # fallback: kalau tidak ada di request, ambil dari session
        fitur = data.get("fitur") or session.get("fitur", "chatbot")
        mode_bahasa = data.get("mode_bahasa") or session.get("mode_bahasa", "Sunda")
        chat_mode = data.get("chat_mode") or session.get("chat_mode", "Ngobrol")
        tingkat_tutur = data.get("tingkat_tutur") or session.get("tingkat_tutur", "Loma")

        try:
            reply = generate_reply(
                prompt=message,
                fitur=fitur,
                mode_bahasa=mode_bahasa,
                chat_mode=chat_mode,
                tingkat_tutur=tingkat_tutur
            )
            
            return jsonify({"reply": reply})
        except Exception as e:
            print("Chat error:", e)
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        print("[ERROR chat_api]", e)
        return jsonify({"reply": f"Maaf, terjadi kesalahan: {e}"})

@chat_bp.route("/chat/delete", methods=["POST"])
def chat_delete():
    if not session.get("user"):
        return jsonify({"error": "unauthorized"}), 401

    user_id = session["user"]["id"]
    try:
        delete_history(user_id, room="default")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@chat_bp.route("/history", methods=["GET"])
def chat_history():
    if not session.get("user"):
        return jsonify([])

    user_id = session["user"]["id"]
    room_id = request.args.get("room_id", "room1")  # <== tambahin ini
    rows = read_history(user_id, room=room_id, limit=50) or []
    history = [
        {"message": h.get("message", ""), "response": h.get("response", "")}
        for h in rows if h.get("message") or h.get("response")
    ]
    return jsonify(history)

@chat_bp.route("/chat/settings", methods=["POST"])
def chat_settings():
    data = request.get_json(force=True) or {}
    fitur = data.get("fitur", "chatbot")
    mode_bahasa = data.get("mode_bahasa", "Sunda")
    chat_mode = data.get("chat_mode", "Ngobrol")
    tingkat_tutur = data.get("tingkat_tutur", "Loma")

    session["fitur"] = fitur
    session["mode_bahasa"] = mode_bahasa
    session["chat_mode"] = chat_mode
    session["tingkat_tutur"] = tingkat_tutur
    session.modified = True

    return jsonify({
        "status": "ok",
        "settings": {
            "fitur": fitur,
            "mode_bahasa": mode_bahasa,
            "chat_mode": chat_mode,
            "tingkat_tutur": tingkat_tutur
        }
    })

@chat_bp.route("/stream", methods=["POST"])
def stream_reply():
    data = request.get_json(force=True) or {}
    prompt = data["message"]

    # Ambil history lama
    history = session.get("history", [])

    # Generate reply
    reply = generate_reply(
        prompt,
        fitur=data.get("fitur"),
        mode_bahasa=data.get("mode_bahasa"),
        chat_mode=data.get("chat_mode"),
        tingkat_tutur=data.get("tingkat_tutur"),
        history=history
    )

    # Simpan history baru
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": reply})
    session["history"] = history

    return jsonify({"reply": reply})

@chat_bp.route("/chat/reply", methods=["POST"])
def chat_reply():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True) or {}
    prompt = data.get("message", "")
    fitur = data.get("fitur", "chatbot")
    mode_bahasa = data.get("mode_bahasa", "Sunda")
    chat_mode = data.get("chat_mode", "Ngobrol")
    tingkat_tutur = data.get("tingkat_tutur", "Loma")
    room_id = data.get("room_id", "room1")

    user_id = session["user"]["id"]

    # Ambil history dari Supabase sesuai room
    history = read_history(user_id, room=room_id, limit=100)

    reply = generate_reply(
        prompt=prompt,
        fitur=fitur,
        mode_bahasa=mode_bahasa,
        chat_mode=chat_mode,
        history=history,
        tingkat_tutur=tingkat_tutur
    )

    # Simpan ke Supabase
    append_chat(
        user_id=session["user"]["id"],
        room=room_id,
        message=prompt,
        response=reply
    )

    # Kalau room belum ada nama → ambil 3 kata pertama dari AI
    if "room_names" not in session:
        session["room_names"] = {}
    if room_id not in session["room_names"]:
        session["room_names"][room_id] = " ".join(reply.split()[:3])
        session.modified = True

    return jsonify({"reply": reply})

@chat_bp.route("/chat/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400

    filename = file.filename
    content = file.read()

    # TODO: ekstrak isi file pdf/doc/image → simpan sebagai konteks
    # contoh: kirim ke AI dengan tambahan prompt "Gunakan dokumen terlampir sebagai referensi"

    return jsonify({"reply": f"File {filename} berhasil diupload dan akan dipakai sebagai referensi."})
