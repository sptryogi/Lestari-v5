
from supabase_helper import (
    load_supabase, sign_in_with_email, sign_up_with_email, sign_out,
    get_user_session, save_chat_message, get_chat_history
)
from flask import session

supabase = load_supabase()

def delete_history(user_id: str, room: str = "default"):
    try:
        response = supabase.table("chat_history").delete().eq("user_id", user_id).eq("room", room).execute()
        return response
    except Exception as e:
        print("Error delete_history:", e)
        return None

def login(email, password):
    res = sign_in_with_email(email, password)
    # simpan minimal user dan token agar bisa dipakai kembali
    if res and res.session and res.user:
        session["user"] = {"id": res.user.id, "email": email}
        session["access_token"] = res.session.access_token
        session["refresh_token"] = res.session.refresh_token
        session.permanent = True
        return {"ok": True}
    return {"ok": False, "error": "Login gagal"}

def register(email, password, age: int):
    res = sign_up_with_email(email, password, age)
    if res and res.user:
        return {"ok": True}
    return {"ok": False, "error": "Registrasi gagal"}

def logout():
    try:
        sign_out()
    finally:
        for k in ["user", "access_token", "refresh_token"]:
            session.pop(k, None)

def append_chat(user_id, message, response, room="default", response_raw=None):
    return save_chat_message(user_id, message, response, room=room, response_raw=response_raw)

def read_history(user_id, room="default", limit=100):
    return get_chat_history(user_id, room=room, limit=limit)


