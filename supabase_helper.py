from supabase import create_client, Client
import time
# from supabase.lib.auth_client import SupabaseAuthException
from httpx import RequestError
import os


# import config
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def load_supabase():  
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
# supabase = load_supabase()
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def sign_in_with_email(email, password):
    return supabase.auth.sign_in_with_password({"email": email, "password": password})

def sign_up_with_email(email, password, age):
    result = supabase.auth.sign_up({"email": email, "password": password})
    user_id = result.user.id
    supabase.table("profiles").insert({"id": user_id, "age": age}).execute()
    return result

def sign_out():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print("Supabase logout gagal:", e)

def get_user_session():
    return supabase.auth.get_session()

def get_user_chat_rooms(user_id):
    result = supabase.table("chat_history") \
        .select("room") \
        .eq("user_id", user_id) \
        .execute()
    if result.data:
        rooms = list(set([r["room"] for r in result.data]))
        return sorted(rooms)
    return []

# def create_chat_room(user_id, room_name):
#     """
#     Membuat entri room baru di database dengan pesan kosong
#     untuk memastikan room muncul di daftar.
#     """
#     try:
#         supabase.table("chat_history").insert({
#             "user_id": user_id,
#             "room": room_name,
#             "message": "",
#             "response": ""
#         }).execute()
#         return {"status": "success"}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

def delete_chat_room(user_id, room_name):
    supabase.table("chat_history") \
        .delete() \
        .eq("user_id", user_id) \
        .eq("room", room_name) \
        .execute()

def insert_chat_history(user_id, room, message, response):
    supabase.table("chat_history").insert({
        "user_id": user_id,
        "room": room,
        "message": message,
        "response": response
    }).execute()

def fetch_chat_history(user_id, room):
    result = supabase.table("chat_history") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("room", room) \
        .order("created_at", desc=False) \
        .execute()
    return result.data if result else []

# Fungsi untuk menyimpan chat history
def save_chat_message(user_id, message, response, room="default", response_raw=None):
    # Cek jumlah history chat dulu
    result = supabase.table("chat_history") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .eq("room", room) \
        .execute()

    if result.count >= 100:
        return {"error": "limit_exceeded"}

    # Jika belum penuh, simpan
    supabase.table("chat_history").insert({
        "user_id": user_id,
        "message": message,
        "response": response,
        "response_raw": response_raw,
        "room": room
    }).execute()

    return {"status": "success"}

# Fungsi untuk mengambil chat history
def get_chat_history(user_id, room="default", limit=100):
    result = supabase.table("chat_history") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("room", room) \
        .order("created_at", desc=False) \
        .limit(limit) \
        .execute()
    return result.data if result else []

def get_first_chat_preview(user_id, room):
    retry = 3
    last_error = None

    for _ in range(retry):
        try:
            result = supabase.table("chat_history") \
                .select("message, response") \
                .eq("user_id", user_id) \
                .eq("room", room) \
                .order("created_at", desc=False) \
                .limit(1) \
                .execute()

            data = getattr(result, "data", None) or []
            if len(data) == 0:
                return "Chat kosong..."

            row = data[1] or {}
            msg = (row.get("message") or "").strip()
            res = (row.get("response") or "").strip()
            text = res or msg
            return (" ".join(text.split()[:5]) + "...") if text else "Chat kosong..."

        except IndexError as e:
            last_error = e
            time.sleep(0.3)
        except RequestError as e:
            last_error = e
            time.sleep(0.5)
        except Exception as e:
            last_error = e
            time.sleep(0.5)

    # Jangan menghentikan UI; anggap kosong kalau tetap error
    print(f"Gagal memuat chat pertama dari Supabase (dianggap kosong). Error: {last_error}")
    return "Chat kosong..."

def _parse_room_num(room_id: str) -> int:
    try:
        return int(str(room_id).split("-")[1])
    except Exception:
        return 0

def create_empty_room(user_id, room_name):
    # Insert 1 baris kosong supaya room muncul di daftar & preview "Chat kosong..."
    supabase.table("chat_history").insert({
        "user_id": user_id,
        "room": room_name,
        "message": "",
        "response": ""
    }).execute()

def ensure_at_least_one_empty_room(user_id):
    """
    Pastikan selalu ada minimal 1 room kosong untuk user ini.
    Return: daftar room terbaru (termasuk yang baru dibuat jika perlu).
    """
    rooms = get_user_chat_rooms(user_id)
    if not rooms:
        create_empty_room(user_id, "room-1")
        return ["room-1"]

    has_empty = False
    for r in rooms:
        if get_first_chat_preview(user_id, r) == "Chat kosong...":
            has_empty = True
            break

    if not has_empty:
        next_num = max([_parse_room_num(r) for r in rooms] + [0]) + 1
        new_room = f"room-{next_num}"
        create_empty_room(user_id, new_room)
        rooms.append(new_room)

    return sorted(set(rooms), key=_parse_room_num)