from openai import OpenAI
import os
from flask import session
import re
import string
from supabase_helper import *
import requests
import json
import fitz  # PyMuPDF
import docx
import time
import tiktoken
from datetime import datetime
import random
from utils.kamus_loader import load_kamus_dan_idiom
from constraint1 import highlight_text, ganti_semua_ke_halus_preserve, ganti_semua_ke_loma_preserve, substitusi_dari_arti_ekuivalen, lema_arti_mirip, ganti_sinonim_berdasarkan_tingkat
# refine_ks_translation, terjemahkan_dengan_KS, terjemahkan_sunda_indo_KS, bandingkan_terjemahan_sunda_indo, revisi_dari_perbedaan_sunda_indo, bandingkan_terjemahan, revisi_dari_perbedaan
import random
import pandas as pd
import numpy as np
import difflib
from unidecode import unidecode
from Levenshtein import distance as lev_dist

# Load sekali saat module di-import
df_kamus, df_idiom, df_pemendekan, df_kosakata, df_majemuk = load_kamus_dan_idiom()


def get_deepseek_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('API_KEY')}"
    }

def call_deepseek_api(prompt, history=None, system_instruction=None,
                      temperature=0.2, top_p=0.9, frequency_penalty=0.0, presence_penalty=0.0):
    api_key = os.getenv("API_KEY")                  
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = get_deepseek_headers()

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    else:
        messages.append({"role": "system", "content": "You are a helpful assistant."})

    if history:
        for msg in history:
            messages.append({"role": "user", "content": msg["message"]})
            messages.append({"role": "assistant", "content": msg["response"]})

    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "stream": False   # ⚠️ paksa non-stream
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print("[ERROR call_deepseek_api]", e)
        return "Maaf, gagal menyambung ke server AI."

def generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history=None, system_instruction=None):
    params = get_params(fitur, chat_mode)   # fungsi kecil utk pilih temperature dll
    formatted_history = [
        {"message": m["message"], "response": m["response"]}
        if isinstance(m, dict) else {"message": m[0], "response": m[1]}
        for m in history
    ] if history else None

    return call_deepseek_api(
        prompt=user_input,
        history=formatted_history,
        system_instruction=system_instruction,   # diisi oleh generate_text_deepseek
        **params
        )

def get_params(fitur, chat_mode):
    """
    Tentukan parameter default untuk model berdasarkan fitur & chat_mode.
    """
    if fitur == "chatbot" and chat_mode == "Ngobrol":
        return {"temperature": 0.3, "top_p": 0.95, "frequency_penalty": 1.5, "presence_penalty": 0.3}
    elif fitur == "chatbot" and chat_mode == "Belajar":
        return {"temperature": 0.2, "top_p": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0}
    elif fitur in ["terjemahindosunda", "terjemahsundaindo"]:
        return {"temperature": 0.1, "top_p": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0}
    else:
        return {"temperature": 0.3, "top_p": 0.9, "frequency_penalty": 0.2, "presence_penalty": 0.2}

def generate_text_deepseek(user_input, fitur, pasangan_cag, mode_bahasa="Sunda", chat_mode = "Ngobrol", history=None, tingkat_tutur=None, system_instruction=None):

    # try:
    #     response = call_deepseek_api(
    #         user_input,
    #         history=history,
    #         system_instruction=system_instruction,   # <--- PATCH diteruskan
    #         temperature=0.3,
    #         top_p=0.9,
    #         frequency_penalty=0.2,
    #         presence_penalty=0.0
    #     )
    # except Exception as e:
    #     print(f"[ERROR] generate_text_deepseek gagal: {e}")
    #     return f"Maaf, gagal menyambung ke server AI. Silakan coba lagi."


    
    # default hasil
    bot_response = ""
    text_constraint = ""
    pasangan_kata, pasangan_ekuivalen = {}, {}

    # ========== FITUR CHATBOT ==========
    if fitur == "chatbot" and mode_bahasa == "Sunda":
        # --- Belajar + Halus ---
        if chat_mode == "Belajar" and tingkat_tutur == "Halus":
            bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history, system_instruction=system_instruction)
            fungsi_halus = ganti_semua_ke_halus_preserve(bot_response, df_kamus)
            kapitalisasi = kapitalisasi_awal_kalimat(fungsi_halus)
            text_constraint = bersihkan_format(kapitalisasi)

        # --- Belajar + Loma ---
        elif chat_mode == "Belajar" and tingkat_tutur == "Loma":
            bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history, system_instruction=system_instruction)
            fungsi_loma = ganti_semua_ke_loma_preserve(bot_response, df_kamus)
            kapitalisasi = kapitalisasi_awal_kalimat(fungsi_loma)
            text_constraint = bersihkan_format(kapitalisasi)


        # --- Ngobrol + Halus ---
        elif chat_mode == "Ngobrol" and tingkat_tutur == "Halus":
            bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history, system_instruction=system_instruction)
            text_constraint, kata_terdapat, kata_tidak_terdapat, pasangan_kata, pasangan_ekuivalen = highlight_text(
                bot_response, df_kamus, df_idiom, fitur, tingkat_tutur
            )
            text_constraint = substitusi_dari_arti_ekuivalen(text_constraint, df_kamus, tingkat_tutur)
            text_constraint = kapitalisasi_awal_kalimat(text_constraint)

        # --- Ngobrol + Loma ---
        elif chat_mode == "Ngobrol" and tingkat_tutur == "Loma":
            bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history, system_instruction=system_instruction)
            text_constraint, kata_terdapat, kata_tidak_terdapat, pasangan_kata, pasangan_ekuivalen = highlight_text(
                bot_response, df_kamus, df_idiom, fitur, tingkat_tutur
            )
            text_constraint = substitusi_dari_arti_ekuivalen(text_constraint, df_kamus, tingkat_tutur)
            text_constraint = kapitalisasi_awal_kalimat(text_constraint)

        # --- Default (Guru atau lainnya) ---
        else:
            bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history, system_instruction=system_instruction)
            text_constraint = bot_response

    elif fitur == "chatbot" and (mode_bahasa == "Indonesia" or mode_bahasa == "English"):
        bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history, system_instruction=system_instruction)
        text_constraint = bot_response

    # ========== FITUR TERJEMAH ==========
    elif fitur == "terjemahsundaindo":
        bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history=None, system_instruction=system_instruction)
        ks_raw, status_majemuk = terjemahkan_sunda_indo_KS(user_input, df_kamus, df_majemuk)
        ks_ai = refine_ks_translation(ks_raw)
        perbedaan = bandingkan_terjemahan_sunda_indo(bot_response, ks_ai)
        text_constraint = revisi_dari_perbedaan_sunda_indo(bot_response, ks_ai, perbedaan, status_majemuk)
        text_constraint = kapitalisasi_awal_kalimat(text_constraint)

    elif fitur == "terjemahindosunda":
        bot_response = generate_core(user_input, fitur, pasangan_cag, mode_bahasa, chat_mode, history=None, system_instruction=system_instruction)
        ks_response = terjemahkan_dengan_KS(user_input, df_kamus, df_majemuk)
        daftar_perbedaan = bandingkan_terjemahan(bot_response, ks_response)
        text_constraint = revisi_dari_perbedaan(
            bot_response, ks_response, daftar_perbedaan, df_kamus, df_majemuk
        )
        text_constraint = lema_arti_mirip(text_constraint, df_kamus)
        text_constraint = ganti_sinonim_berdasarkan_tingkat(text_constraint, df_kamus)
        text_constraint, kata_terdapat, kata_tidak_terdapat, pasangan_kata, pasangan_ekuivalen = highlight_text(
            text_constraint, df_kamus, df_idiom, fitur, tingkat_tutur=None
        )
        text_constraint = kapitalisasi_awal_kalimat(text_constraint)

    else:
        text_constraint = "Fitur belum didukung."

    return text_constraint


def bersihkan_superscript(teks):
    # Menghapus superscript angka ¹²³⁴⁵⁶⁷⁸⁹⁰ atau angka biasa setelah huruf
    return re.sub(r'([^\d\s])[\u00B9\u00B2\u00B3\u2070\u2074-\u2079\d]+', r'\1', teks)

def kapitalisasi_awal_kalimat(teks):
    # Bersihkan superscript dulu
    teks = bersihkan_superscript(teks)

    # Pecah berdasarkan paragraf (baris kosong)
    paragraf_list = teks.split("\n\n")
    paragraf_hasil = []

    for paragraf in paragraf_list:
        # Bagi kalimat dalam paragraf berdasarkan tanda baca yang diikuti spasi atau akhir kalimat
        kalimat_list = re.split(r'([.!?]["\']?\s+)', paragraf)
        kalimat_terformat = ""

        for i in range(0, len(kalimat_list), 2):
            if i < len(kalimat_list):
                kalimat = kalimat_list[i].strip()
                if kalimat:
                    kapital = kalimat[0].upper() + kalimat[1:] if len(kalimat) > 1 else kalimat.upper()
                    kalimat_terformat += kapital
            if i + 1 < len(kalimat_list):
                kalimat_terformat += kalimat_list[i+1]

        paragraf_hasil.append(kalimat_terformat.strip())

    # Gabungkan kembali paragraf dengan \n\n
    return "\n\n".join(paragraf_hasil)

def hitung_token(teks):
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(teks))

# reader = easyocr.Reader(['id', 'en'])  # Tambahkan 'su' untuk Bahasa Sunda

def ekstrak_teks(file):
    if file.type == "application/pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file.read(), filetype="pdf")
        return "\n".join(page.get_text() for page in doc)

    elif file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        import docx
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])

    elif file.type.startswith("image/"):
        # from PIL import Image
        # import numpy as np
        # img = Image.open(file).convert("RGB")
        # img_array = np.array(img)
        # results = reader.readtext(img_array, detail=0)
        # return "\n".join(results)
        return "[Gambar terlampir, tidak diproses sebagai teks]"

    else:
        return "❌ Jenis file tidak didukung."

import re

def bersihkan_format(teks: str) -> str:
    """
    Bersihkan format aneh dari constraint, hapus tag HTML, 
    hilangkan duplikat, rapikan paragraf Jawaban & Penjelasan.
    """

    # 1. Hilangkan tag <i>, <b>, <u>, dll
    teks = re.sub(r'</?(i|b|u|bi|ii)[^>]*>', '', teks)

    # 2. Hilangkan sisa markup <<...>> atau tag aneh
    teks = re.sub(r'<<[^>]+>>', '', teks)

    # 3. Rapikan label "Jawaban" & "Penjelasan" biar satu kali saja
    teks = re.sub(r'(\*\*Jawaban:\*\*)(\s*\*\*Jawaban:\*\*)+', r'**Jawaban:**', teks, flags=re.I)
    teks = re.sub(r'(\*\*Penjelasan:\*\*)(\s*\*\*Penjelasan:\*\*)+', r'**Penjelasan:**', teks, flags=re.I)

    # 4. Pastikan Jawaban & Penjelasan di baris baru
    # Pisahkan label Jawaban & Penjelasan biar ke baris baru
    teks = re.sub(r'\*\*Jawaban:\*\*', r'\n\n**Jawaban:**\n', teks)
    teks = re.sub(r'\*\*Penjelasan:\*\*', r'\n\n**Penjelasan:**\n', teks)

    # 5. Hilangkan baris kosong berlebih
    teks = re.sub(r'\n{3,}', '\n\n', teks)

    # 6. Strip spasi awal/akhir
    return teks.strip()

# def pilih_berdasarkan_konteks_llm(kandidat_list, kalimat_asli, kata_typo_asli):
#     if not kandidat_list:
#         return None

#     daftar_kandidat = ", ".join(kandidat_list)
#     prompt = f"""
#             Kalimat berikut mengandung kata salah tulis:
            
#             "{kalimat_asli}"
            
#             Bagian yang salah adalah: "{kata_typo_asli}" (ditulis dalam tag <i>...</i>).
            
#             Berikut adalah daftar kandidat koreksi (dari kamus): {daftar_kandidat}.
            
#             Pilih satu kata yang paling sesuai secara makna dengan konteks kalimat tersebut.
#             Jawab hanya dengan satu kata dari daftar, tanpa penjelasan dan jangan memberikan catatan.
#             """
#     hasil = call_deepseek_api(prompt, history=None,  system_instruction=None)  # Atau Groq, OpenAI
#     hasil_bersih = hasil.strip().lower()

#     if hasil_bersih in kandidat_list:
#         return hasil_bersih
#     return None

# def apakah_nama_diri(typo):
#     prompt = f"""Apakah "{typo}" adalah nama orang atau nama tempat (geografis)? 
#                  Jawab dengan salah satu kata berikut saja:
#                  - nama orang
#                  - nama tempat
#                  - bukan

#                  Contoh:
#                  - Jakarta → nama tempat
#                  - Siti → nama orang
#                  - Rumah Makan → nama tempat
#                  - Kolam Renang → nama tempat
#                  - meja → bukan

#                 Sekarang, jawab untuk kata: {typo}"""
#     try:
#         jawaban = call_deepseek_api(prompt).lower()
#         return "nama orang" in jawaban or "nama tempat" in jawaban
#     except:
#         return False  # Jika error, anggap bukan nama
valid_sequence = {
    "N": ["V", "Adj", "P", "Pro", None],
    "Pro": ["V", "Adj", "Adv", "P", "Modal", None],
    "V": ["N", "Pro", "Num", "Adv", "Adj", None],
    "Adj": ["P", "N", None],
    "Adv": ["V", "Adj", "Adv", "Modal", None],
    "Num": ["N", None],
    "P": ["N", "V", "Adj", "Pro", "Modal", None],
    "Modal": ["V", None],
    None: ["N", "V", "Adj", "P", "Pro", "Adv", "Num", "Modal", None],
}

def cek_valid_urutan(kelas_hasil, klas_sekarang, valid_sequence):
    """Cek apakah kelas kata sekarang valid berdasarkan kelas kata sebelumnya."""
    kelas_sebelum = kelas_hasil[-1] if kelas_hasil else None
    allowed_next = valid_sequence.get(kelas_sebelum, valid_sequence[None])
    return klas_sekarang in allowed_next

def terjemahkan_dengan_KS(teks_indo, df_kamus, df_majemuk):
    """
    Terjemahkan teks Indo → Sunda:
    1. Cek frasa 2 kata di df_majemuk (EKUIVALEN → LEMA).
    2. Kalau tidak ada, cek frasa 2 kata di df_kamus (EKUIVALEN 1 / 2 → LEMA/SUBLEMA).
    3. Kalau tidak ada, cek per kata:
       - EKUIVALEN 1 / 2
       - ARTI 1 (hanya jika berupa 1 kata atau daftar sinonim dipisahkan koma)
    4. Kalau tidak ada juga, pakai kata asal.
    """
    hasil = []
    kelas_hasil = []
    tokens = re.findall(r'\w+|\d+\.|[^\w\s]', teks_indo, re.UNICODE)
    i = 0

    while i < len(tokens):
        kandidat_sunda = None
        kandidat_klas = None

        # === STEP 1 & 2: cek frasa 2 kata ===
        if i + 1 < len(tokens):
            dua_kata = f"{tokens[i]} {tokens[i+1]}".lower()

            # cek di df_majemuk
            cocok_maj = df_majemuk[df_majemuk["EKUIVALEN"].str.lower() == dua_kata]
            if not cocok_maj.empty:
                lema = cocok_maj.iloc[0]["LEMA"]
                klas = cocok_maj.iloc[0].get("KLAS.", None)
                if cek_valid_urutan(kelas_hasil, klas, valid_sequence):
                    kandidat_sunda, kandidat_klas = lema, klas
                else:
                    kandidat_sunda, kandidat_klas = lema, klas  # fallback
            else:
                # cek di df_kamus (EKUIVALEN 1/2)
                cocok_dua = df_kamus[
                    (df_kamus["EKUIVALEN 1"].str.lower() == dua_kata) |
                    (df_kamus["EKUIVALEN 2"].str.lower() == dua_kata)
                ]
                if not cocok_dua.empty:
                    kandidat_valid = None
                    kandidat_fallback = None
                    for idx, row in cocok_dua.iterrows():
                        lema = row["LEMA"] or row["SUBLEMA"]
                        klas = row.get("KLAS.", None)
                        if cek_valid_urutan(kelas_hasil, klas, valid_sequence):
                            kandidat_valid = (lema, klas)
                            break
                        elif not kandidat_fallback:
                            kandidat_fallback = (lema, klas)

                    if kandidat_valid:
                        kandidat_sunda, kandidat_klas = kandidat_valid
                    elif kandidat_fallback:
                        kandidat_sunda, kandidat_klas = kandidat_fallback

            if kandidat_sunda:
                hasil.append(kandidat_sunda)
                kelas_hasil.append(kandidat_klas)
                i += 2
                continue

        # === STEP 3: cek per kata (EKUIVALEN + ARTI 1) ===
        satu_kata = tokens[i].lower()
        cocok_satu = df_kamus[
            (df_kamus["EKUIVALEN 1"].str.lower() == satu_kata) |
            (df_kamus["EKUIVALEN 2"].str.lower() == satu_kata)
        ]

        # Tambahan: cek ARTI 1
        cocok_arti = df_kamus[df_kamus["ARTI 1"].notna()]
        cocok_arti = cocok_arti[cocok_arti["ARTI 1"].apply(
            lambda x: any(satu_kata == kandidat.strip().lower() for kandidat in x.split(","))
                       if ("," in x or len(x.split()) == 1) else False
        )]

        kandidat_rows = pd.concat([cocok_satu, cocok_arti]).drop_duplicates()

        if not kandidat_rows.empty:
            kandidat_valid = None
            kandidat_fallback = None
            for idx, row in kandidat_rows.iterrows():
                lema = row["LEMA"] or row["SUBLEMA"]
                klas = row.get("KLAS.", None)

                if cek_valid_urutan(kelas_hasil, klas, valid_sequence):
                    kandidat_valid = (lema, klas)
                    break
                elif not kandidat_fallback:
                    kandidat_fallback = (lema, klas)

            if kandidat_valid:
                kandidat_sunda, kandidat_klas = kandidat_valid
            elif kandidat_fallback:
                kandidat_sunda, kandidat_klas = kandidat_fallback

            if kandidat_sunda:
                hasil.append(kandidat_sunda)
                kelas_hasil.append(kandidat_klas)
            else:
                hasil.append(tokens[i])  # fallback ke kata asal
                kelas_hasil.append(None)
        else:
            hasil.append(tokens[i])  # fallback ke kata asal
            kelas_hasil.append(None)

        i += 1

    # Gabungkan ulang
    kalimat_akhir = ''
    for j, token in enumerate(hasil):
        if j > 0 and re.fullmatch(r'\w+', token) and re.fullmatch(r'\w+', hasil[j-1]):
            kalimat_akhir += ' '
        kalimat_akhir += token

    return kalimat_akhir.strip()
    
def bandingkan_terjemahan(bot_response, ks_response):
    token_bot = re.findall(r'\w+|\d+\.|[^\w\s]', bot_response.lower())
    token_ks = re.findall(r'\w+|\d+\.|[^\w\s]', ks_response.lower())

    perbedaan = []
    i = j = 0
    while i < len(token_ks) and j < len(token_bot):
        ks = token_ks[i]
        bot = token_bot[j]

        if ks == bot:
            i += 1
            j += 1
        else:
            # 🔹 Cek jika 2 token KS = 1 token BOT (majemuk → padat)
            if i + 1 < len(token_ks) and f"{token_ks[i]} {token_ks[i+1]}" == bot:
                perbedaan.append((f"{token_ks[i]} {token_ks[i+1]}", bot))
                i += 2
                j += 1
            # 🔹 Cek sebaliknya: 2 token BOT = 1 token KS (padat → majemuk)
            elif j + 1 < len(token_bot) and f"{token_bot[j]} {token_bot[j+1]}" == ks:
                perbedaan.append((ks, f"{token_bot[j]} {token_bot[j+1]}"))
                i += 1
                j += 2
            else:
                perbedaan.append((ks, bot))
                i += 1
                j += 1

    return perbedaan

def kata_masih_indonesia(kata, df_kamus):
    # True jika kata belum ada di kolom LEMA/SUBLEMA
    kata_norm = kata.lower().strip()
    cocok = df_kamus[
        (df_kamus['LEMA'].str.lower() == kata_norm) |
        (df_kamus['SUBLEMA'].str.lower() == kata_norm)
    ]
    return cocok.empty
    
def revisi_dari_perbedaan(hasil_ks, hasil_deepseek, daftar_perbedaan, df_kamus, df_majemuk=None):
    if not daftar_perbedaan:
        return hasil_deepseek

    daftar_str = ""
    for benar, salah in daftar_perbedaan:
        # 1. Jika KS masih bahasa Indonesia → skip, pakai AI
        if kata_masih_indonesia(benar, df_kamus):
            continue

        # 2. Jika benar ada di df_majemuk → prioritaskan KS
        if df_majemuk is not None:
            cocok = df_majemuk[df_majemuk["LEMA"].str.lower() == benar.lower()]
            if not cocok.empty:
                daftar_str += f'- Ganti "{salah}" → "{benar}" (padanan majemuk KS)\n'
                continue

        # 3. Jika versi KS lebih majemuk daripada AI → prioritaskan
        if len(benar.split()) > 1 and len(salah.split()) == 1:
            daftar_str += f'- Ganti "{salah}" → "{benar}"\n'
        else:
            # 4. Kalau bukan majemuk → jadikan opsi saja
            daftar_str += f'- Kata "{salah}" bisa diganti menjadi "{benar}" jika lebih tepat.\n'

    if not daftar_str.strip():
        return hasil_deepseek  # Tidak ada koreksi berarti

    prompt = f"""
    Ini adalah hasil awal terjemahan AI dari kalimat:
    "{hasil_deepseek}"
    
    Dibandingkan dengan hasil terjemahan berbasis kamus:
    "{hasil_ks}"
    
    Terdapat beberapa perbedaan yang sebaiknya ditinjau ulang:
    {daftar_str}

    Tolong revisi hasil terjemahan ini dengan aturan:
    - Prioritaskan kata/frasa dari KS terutama yang majemuk.
    - Jangan gunakan kata Bahasa Indonesia.
    - Jangan ubah nama orang atau nama tempat.
    - Jangan menambahkan kata atau halusinasi.
    - Gunakan Bahasa Sunda umum (LOMA), alami, dan sesuai konteks.
    - Hanya berikan hasil revisi akhir tanpa catatan tambahan.

    Kalimat yang harus direvisi:
    "{hasil_deepseek}"
    """

    prompt += """
    Jika terdapat kalimat langsung (kutipan), gunakan aturan tingkat tutur:
    - Orang tua → anak/istri/teman → LOMA
    - Anak → orang tua/guru/dewasa → HALUS
    - Atasan → bawahan → LOMA
    - Jika tidak jelas relasinya → gunakan netral sesuai konteks.
    Jika tidak ada kalimat langsung, abaikan aturan ini.
    """

    return call_deepseek_api(
        prompt=prompt,
        history=None,
        system_instruction="Kamu adalah ahli penerjemah Bahasa Indonesia ke Bahasa Sunda.",
        temperature=0.1,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
    )

def terjemahkan_sunda_indo_KS(teks_sunda, df_kamus, df_majemuk):
    import re

    tokens = re.findall(r"\w+|[^\w\s]", teks_sunda, re.UNICODE)
    hasil = []
    status_majemuk = False
    i = 0

    while i < len(tokens):
        unigram = tokens[i].lower()
        bigram = " ".join(tokens[i:i+2]).lower()
        trigram = " ".join(tokens[i:i+3]).lower()
        padanan = None

        # === 1. Cek di df_majemuk (trigram dulu, lalu bigram) ===
        row_match = df_majemuk[
            (df_majemuk["LEMA"].str.lower() == trigram) |
            (df_majemuk["HALUS"].str.lower() == trigram)
        ]
        if not row_match.empty:
            padanan = str(row_match.iloc[0].get("EKUIVALEN", "")).strip()
            if padanan:
                hasil.append(padanan)
                i += 3
                status_majemuk = True
                continue

        row_match = df_majemuk[
            (df_majemuk["LEMA"].str.lower() == bigram) |
            (df_majemuk["HALUS"].str.lower() == bigram)
        ]
        if not row_match.empty:
            padanan = str(row_match.iloc[0].get("EKUIVALEN", "")).strip()
            if padanan:
                hasil.append(padanan)
                i += 2
                status_majemuk = True
                continue

        # === 2. Kalau tidak ada → cek di df_kamus (LEMA/SUBLEMA) ===
        row_match = df_kamus[df_kamus["LEMA"].str.lower() == unigram]
        if row_match.empty:
            row_match = df_kamus[df_kamus["SUBLEMA"].str.lower() == unigram]

        if not row_match.empty:
            ekuivalen1 = str(row_match.iloc[0].get("EKUIVALEN 1", "")).strip()
            ekuivalen2 = str(row_match.iloc[0].get("EKUIVALEN 2", "")).strip()
            arti1 = str(row_match.iloc[0].get("ARTI 1", "")).strip()

            if ekuivalen1:
                padanan = ekuivalen1
            elif ekuivalen2:
                padanan = ekuivalen2
            elif arti1:
                padanan = arti1

        # === 3. Kalau tetap tidak ada → pakai kata asal ===
        hasil.append(padanan if padanan else tokens[i])
        i += 1

    # Rapikan tanda baca
    kalimat = " ".join(hasil)
    kalimat = (
        kalimat.replace(" ,", ",")
               .replace(" .", ".")
               .replace(" !", "!")
               .replace(" ?", "?")
    )

    return kalimat, status_majemuk

def refine_ks_translation(teks_ks):
    if not teks_ks.strip():
        return ""

    prompt_refine = f"""
    Berikut adalah hasil terjemahan awal dari bahasa Sunda ke bahasa Indonesia
    yang masih kaku dan kurang natural:

    "{teks_ks}"

    Perbaiki teks ini agar menjadi bahasa Indonesia yang halus, natural, sesuai konteks,
    padu dalam kalimat utuh, tetapi tetap menjaga arti utama.
    Jangan menambahkan informasi baru yang tidak ada.
    Langsung berikan hasilnya saja, tanpa menambahkan hal lain seperti Catatan, Alasan, atau kata awalan, langsung saja to the point.
    """

    hasil_refine = call_deepseek_api(
        prompt=prompt_refine, 
        history=None, 
        system_instruction=None, 
        temperature=0.2, 
        top_p=0.9, 
        frequency_penalty=0.5, 
        presence_penalty=0.2
        )

    return hasil_refine.strip()

def bandingkan_terjemahan_sunda_indo(ai_pure, ks_ai):
    import re
    
    # Tokenisasi sederhana (kata, angka, tanda baca)
    token_ai = re.findall(r'\w+|\d+\.|[^\w\s]', ai_pure.lower())
    token_ks = re.findall(r'\w+|\d+\.|[^\w\s]', ks_ai.lower())

    perbedaan = []
    i = j = 0
    while i < len(token_ks) and j < len(token_ai):
        ks = token_ks[i]
        ai = token_ai[j]

        if ks == ai:
            # Sama → lanjut
            i += 1
            j += 1
        else:
            # Cek kasus 2 KS = 1 AI (frasa → padat)
            if i + 1 < len(token_ks) and f"{token_ks[i]} {token_ks[i+1]}" == ai:
                perbedaan.append((f"{token_ks[i]} {token_ks[i+1]}", ai))
                i += 2
                j += 1
            # Cek kasus 2 AI = 1 KS (padat → frasa)
            elif j + 1 < len(token_ai) and f"{token_ai[j]} {token_ai[j+1]}" == ks:
                perbedaan.append((ks, f"{token_ai[j]} {token_ai[j+1]}"))
                i += 1
                j += 2
            else:
                # Kasus umum → beda kata
                perbedaan.append((ks, ai))
                i += 1
                j += 1

    return perbedaan

def revisi_dari_perbedaan_sunda_indo(ai_pure, ks_ai, perbedaan, status_majemuk):
    # Jika frasa/majemuk → langsung pakai KS
    if status_majemuk:
        return ks_ai  

    # Kalau tidak ada perbedaan, pakai AI Pure saja
    if not perbedaan:
        return ai_pure

    # Susun daftar perbedaan untuk prompt
    daftar_beda = "\n".join([f"- KS: '{ks}' | AI: '{ai}'" for ks, ai in perbedaan])

    prompt_revisi = f"""
    Berikut adalah dua hasil terjemahan dari bahasa Sunda ke bahasa Indonesia:

    1. AI Pure (langsung dari AI):
    {ai_pure}

    2. KS+AI (kamus lalu dipoles AI):
    {ks_ai}

    Perbedaan kata/frasa:
    {daftar_beda}

    Aturan revisi:
    - Prioritaskan hasil dari AI Pure karena lebih natural.
    - Gunakan padanan dari KS jika hasil AI kurang tepat, janggal, atau tidak sesuai konteks.
    - Hasilkan kalimat final dalam bahasa Indonesia yang halus, natural, dan sesuai konteks.
    - Hanya berikan hasil revisi akhir tanpa catatan tambahan seperti note, catatan, atau kata awalan.
    """

    hasil_final = call_deepseek_api(
        prompt=prompt_revisi,
        history=None,
        system_instruction=None,
        temperature=0.2,    # stabil, tidak ngawur
        top_p=0.9,
        frequency_penalty=0.5,
        presence_penalty=0.2
    )

    return hasil_final.strip()

