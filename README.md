
# Lestari Bahasa — Flask Refactor

Migrasi dari Streamlit ke Flask + Tailwind + JS dengan UI mirip ChatGPT.

## Struktur
```
chatbot_flask/
├─ app.py
├─ config.py
├─ supabase_flask.py
├─ services/
│  └─ chatbot_service.py
├─ blueprints/
│  ├─ auth.py
│  ├─ chat.py
│  └─ sundalex.py
├─ templates/
│  ├─ base.html
│  ├─ login.html
│  ├─ chat.html
│  └─ sundalex.html
├─ static/
│  ├─ style.css
│  └─ script.js
└─ requirements.txt
```

## Menjalankan
1. Pastikan modul lama (`AI_chatbot.py`, `constraint1.py`, `supabase_helper.py`, dataset/) ada di *root project* yang sama ini.
2. Buat env: `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
3. Install deps: `pip install -r requirements.txt`
4. Jalankan: `python app.py`
5. Buka `http://localhost:5000`

> Catatan: `SECRET_KEY` di `app.py` wajib diganti. Supabase URL/KEY sebaiknya via ENV.
