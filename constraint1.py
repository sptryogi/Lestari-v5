import random
import re
import pandas as pd
import numpy as np
import difflib
from unidecode import unidecode
from Levenshtein import distance as lev_dist

 # ================= PENGURAIAN SUBLEMA =================
def substitusi_dari_ekuivalen1(teks, df_kamus):
    """
    Fungsi untuk mencari padanan kata italic dari EKUIVALEN dan menggantinya
    dengan kata dari kolom LEMA atau SUBLEMA di baris yang sama.
    Jika (HALUS/LOMA/KASAR) bernilai HALUS, hasilnya dibold, kalau tidak, cetak biasa.
    """
    pola_italic = r"<i>(.*?)</i>"

    def ganti_kata_italic(match):
        kata = match.group(1).strip()
        # Cek di EKUIVALEN
        mask_eq = (
            df_kamus["EKUIVALEN 1"].astype(str).str.lower() == kata.lower()
        ) | (
            df_kamus["EKUIVALEN 2"].astype(str).str.lower() == kata.lower()
        )
        row_eq = df_kamus[mask_eq]
        if not row_eq.empty:
            # Tukar ke LEMA atau SUBLEMA
            kata_ganti = row_eq.iloc[0]["LEMA"] if pd.notna(row_eq.iloc[0]["LEMA"]) else row_eq.iloc[0]["SUBLEMA"]
            tingkat_tutur = row_eq.iloc[0]["(HALUS/LOMA/KASAR)"]
            if pd.notna(kata_ganti):
                if isinstance(tingkat_tutur, str) and "HALUS" in tingkat_tutur.upper():
                    return f"<b>{kata_ganti}</b>"
                else:
                    return kata_ganti  # Cetak biasa
        # Tidak ketemu → tetap italic
        return match.group(0)

    # Proses substitusi
    teks_baru = re.sub(pola_italic, ganti_kata_italic, teks)
    return teks_baru
    
def bersihkan_teks(teks):
    # Menghapus semua karakter kecuali huruf, angka, spasi, dan tanda minus
    return re.sub(r'[^A-Za-z0-9\s-]', '', teks)
 
def bersihkan_kamus(df):
    """
    Bersihkan kamus dari nilai NaN yang bisa berubah menjadi 'nan' string,
    serta pastikan kolom-kolom penting tidak mengandung nilai kosong.

    - Ganti NaN dengan "" di kolom teks seperti: LEMA, SUBLEMA, SINONIM, CONTOH KALIMAT, dll.
    - Lowercase opsional juga bisa di sini kalau konsisten.
    """
    kolom_teks = ["LEMA", "SUBLEMA"]

    for kolom in kolom_teks:
        if kolom in df.columns:
            df[kolom] = df[kolom].fillna("").astype(str)
    
    return df
 
def bersihkan_superscript(teks):
    # Menghapus superscript angka ¹²³⁴⁵⁶⁷⁸⁹⁰ atau angka biasa setelah huruf
    return re.sub(r'([^\d\s])[\u00B9\u00B2\u00B3\u2070\u2074-\u2079\d]+', r'\1', teks)
 
def normalisasi_teks(text):
    return unidecode(text.lower().strip())

def pecah_arti_ekuivalen(arti_raw):
    # Boleh satu kata atau frasa, pisahkan berdasarkan koma
    return [normalisasi_teks(a) for a in re.split(r",|\n", str(arti_raw)) if a.strip()]

def rasio_typo_diterima(salah, benar, max_jarak=1):
    return lev_dist(salah, benar) <= max_jarak and lev_dist(salah, benar) <= round(0.25 * len(benar))

def koreksi_typo_dari_respon(teks_ai, df_kamus_lengkap, df_kamus_pemendekan):
    lema_list = df_kamus_lengkap["LEMA"].dropna().apply(normalisasi_teks).unique()
    sublema_list = df_kamus_lengkap["SUBLEMA"].dropna().apply(normalisasi_teks).unique()
    semua_lema_sublema = list(set(lema_list) | set(sublema_list))

    semua_pemendekan = df_kamus_pemendekan["PEMENDEKAN"].dropna().apply(normalisasi_teks).unique()
    arti_ke_pemendekan = {}
    semua_arti_pemendekan = set()

    for _, row in df_kamus_pemendekan.iterrows():
        pemendekan = row.get("PEMENDEKAN")
        arti_raw = row.get("EKUIVALEN 1")
        if pd.notna(arti_raw) and pd.notna(pemendekan):
            arti_list = pecah_arti_ekuivalen(arti_raw)
            for arti in arti_list:
                arti_ke_pemendekan[arti] = normalisasi_teks(pemendekan)
                semua_arti_pemendekan.add(arti)

    arti_ke_lema_multi = {}
    semua_arti = set()
    kata_ke_klas = {}
    tingkat_tutur = {}

    for _, row in df_kamus_lengkap.iterrows():
        lemma = row.get("LEMA")
        sublema = row.get("SUBLEMA")
        arti_raw = row.get("EKUIVALEN 1") or row.get("EKUIVALEN 2")
        klas = row.get("KLAS.")
        tingkat = str(row.get("(HALUS/LOMA/KASAR)")) if pd.notna(row.get("(HALUS/LOMA/KASAR)")) else ""

        target_kata = lemma or sublema
        if pd.notna(target_kata):
            kata_norm = normalisasi_teks(target_kata)
            kata_ke_klas[kata_norm] = str(klas).strip() if pd.notna(klas) else None
            tingkat_tutur[kata_norm] = tingkat.lower()

        if pd.notna(arti_raw) and target_kata:
            arti_list = pecah_arti_ekuivalen(arti_raw)
            for arti in arti_list:
                arti_norm = normalisasi_teks(arti)
                if arti_norm not in arti_ke_lema_multi:
                    arti_ke_lema_multi[arti_norm] = []
                arti_ke_lema_multi[arti_norm].append(kata_norm)
                semua_arti.add(arti_norm)

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

    def is_valid_pos(kandidat, sebelum, sesudah):
        pos_kandidat = kata_ke_klas.get(kandidat)
        pos_sebelum = kata_ke_klas.get(sebelum)
        pos_sesudah = kata_ke_klas.get(sesudah)
        valid_after = valid_sequence.get(pos_sebelum, valid_sequence[None])
        valid_before = valid_sequence.get(pos_kandidat, valid_sequence[None])
        return (pos_kandidat in valid_after) and (pos_sesudah in valid_before)

    def prioritaskan_tingkat(kandidat_list):
        def nilai_tingkat(k):
            t = tingkat_tutur.get(k, "")
            if "loma" in t: return 0
            if "halus" in t: return 1
            return 2
        return sorted(kandidat_list, key=lambda k: (nilai_tingkat(k), k))

    pola_italic = re.compile(r"<i>(.*?)</i>")
    parts = pola_italic.split(teks_ai)
    hasil = []

    for i, part in enumerate(parts):
        if i % 2 == 1:
            typo = part.strip()
            if apakah_nama_diri(typo):
                hasil.append(f"{typo}")
                continue
            if re.fullmatch(r"[A-Z]{2,5}", typo):  # misalnya: UNS, ITB, DPR
                hasil.append(f"{typo}")
                continue
            if re.search(r'\b(Jl|Dr|Ir|SH|MH|M\.Hum|H|Prof|KH|MT|M\.Si|SE|Sp\.|MA|Ph\.D|MBA|BSc|S\.Pd|S\.H|M\.Pd)\b', typo, re.IGNORECASE):
                hasil.append(f"{typo}")
                continue
            # 💡 Jika typo adalah singkatan kapital pendek, abaikan
            if re.fullmatch(r"[A-Z]{2,5}(\.[A-Z]{1,3})?", typo):  # Misal: DPR, M.Hum
                hasil.append(f"{typo}")
                continue
            typo_bersih = re.sub(r"[^\w-]", "", normalisasi_teks(typo))

            sebelum = re.sub(r"[^\w-]", "", normalisasi_teks(parts[i - 1].split()[-1])) if i - 1 >= 0 and parts[i - 1].split() else None
            sesudah = re.sub(r"[^\w-]", "", normalisasi_teks(parts[i + 1].split()[0])) if i + 1 < len(parts) and parts[i + 1].split() else None

            if typo_bersih in semua_pemendekan:
                hasil.append(f"<b>{typo_bersih}</b>")
                continue

            if typo_bersih in arti_ke_pemendekan:
                hasil.append(f"<b>{arti_ke_pemendekan[typo_bersih]}</b>")
                continue

            if typo_bersih in semua_lema_sublema:
                hasil.append(f"<b>{typo_bersih}</b>")
                continue

            if typo_bersih in arti_ke_lema_multi:
                kandidat_dari_arti = arti_ke_lema_multi[typo_bersih]
                kandidat_dari_arti = prioritaskan_tingkat(kandidat_dari_arti)
                hasil.append(f"<b>{kandidat_dari_arti[0]}</b>")
                continue

            kandidat_difflib = difflib.get_close_matches(typo_bersih, semua_lema_sublema, n=10, cutoff=0.85)
            kandidat_lev = [k for k in semua_lema_sublema if lev_dist(typo_bersih, k) <= 1]
            kandidat_semua = list(set(kandidat_difflib + kandidat_lev))

            kandidat_semua = prioritaskan_tingkat(kandidat_semua)
            kandidat_semua.sort(key=lambda k: (0 if is_valid_pos(k, sebelum, sesudah) else 1, lev_dist(typo_bersih, k)))

            if kandidat_semua:
                pilihan = pilih_berdasarkan_konteks_llm(kandidat_semua[:5], teks_ai, typo)
                if pilihan:
                    hasil.append(f"<b>{pilihan}</b>")
                    continue

            kandidat_arti = difflib.get_close_matches(typo_bersih, list(semua_arti), n=5, cutoff=0.85)
            kandidat_arti_lev = [a for a in semua_arti if lev_dist(typo_bersih, a) <= 1]
            kandidat_arti_final = list(set(kandidat_arti + kandidat_arti_lev))
            kandidat_arti_final.sort(key=lambda x: lev_dist(typo_bersih, x))

            if kandidat_arti_final:
                pilihan_arti = pilih_berdasarkan_konteks_llm(kandidat_arti_final[:5], teks_ai, typo)
                if pilihan_arti and pilihan_arti in arti_ke_lema_multi:
                    kandidat_dari_arti = prioritaskan_tingkat(arti_ke_lema_multi[pilihan_arti])
                    hasil.append(f"<b>{kandidat_dari_arti[0]}</b>")
                    continue

            hasil.append(f"<i>{typo}</i>")
        else:
            hasil.append(part)

    return "".join(hasil)
 
def ganti_sinonim_berdasarkan_tingkat(teks, df_kamus):
    pola = r'"([^"]+)"'
    kutipan_list = re.findall(pola, teks)

    for kutipan in kutipan_list:
        kata_kutipan = kutipan.split()
        tingkat_kata = []

        for kata in kata_kutipan:
            kata_bersih = re.sub(r"[^\w-]", "", kata.lower())
            cocok = df_kamus[
                (df_kamus['LEMA'].str.lower() == kata_bersih) |
                (df_kamus['SUBLEMA'].str.lower() == kata_bersih)
            ]
            if not cocok.empty:
                tingkat_kata += cocok['(HALUS/LOMA/KASAR)'].dropna().tolist()

        if not tingkat_kata:
            continue

        tingkat_kata = [t.lower() for t in tingkat_kata]
        dominan_halus = sum(t in ['halus', 'halus/loma', 'loma/halus'] for t in tingkat_kata)
        dominan_loma = sum(t in ['loma', 'loma/halus', 'loma/kasar'] for t in tingkat_kata)
        total = dominan_halus + dominan_loma
        if total == 0:
            continue

        persen_halus = dominan_halus / total
        persen_loma = dominan_loma / total

        if persen_halus >= 0.51:
            kategori = 'halus'
            kategori_filter = ['halus', 'halus/loma', 'loma/halus']
        elif persen_loma >= 0.51:
            kategori = 'loma'
            kategori_filter = ['loma', 'loma/halus', 'loma/kasar']
        else:
            continue

        kata_baru = []
        for kata in kata_kutipan:
            tanda = re.findall(r'[.,!?]$', kata)
            suffix = tanda[0] if tanda else ''
            kata_bersih = re.sub(r"[^\w-]", "", kata.lower())

            row_kamus = df_kamus[
                (df_kamus['LEMA'].str.lower() == kata_bersih) |
                (df_kamus['SUBLEMA'].str.lower() == kata_bersih)
            ]
            diganti = False

            if not row_kamus.empty:
                tingkat_asal = str(row_kamus.iloc[0]['(HALUS/LOMA/KASAR)']).lower()
                # Skip jika sudah sesuai kategori
                if kategori == 'halus' and tingkat_asal in ['halus', 'halus/loma', 'loma/halus']:
                    kata_baru.append(kata)
                    continue
                elif kategori == 'loma' and tingkat_asal in ['loma', 'loma/halus', 'loma/kasar']:
                    kata_baru.append(kata)
                    continue

                sinonim_raw = row_kamus.iloc[0]['SINONIM'] if 'SINONIM' in row_kamus.columns else ""
                if pd.notna(sinonim_raw):
                    sinonim_list = [s.strip().lower() for s in re.split(r'[.,]', sinonim_raw) if s.strip()]
                    for s in sinonim_list:
                        match_row = df_kamus[
                            ((df_kamus['LEMA'].str.lower() == s) | (df_kamus['SUBLEMA'].str.lower() == s)) &
                            (df_kamus['(HALUS/LOMA/KASAR)'].str.lower().isin(kategori_filter))
                        ]
                        if not match_row.empty:
                            lemma_atau_sub = match_row.iloc[0]['LEMA'] if pd.notna(match_row.iloc[0]['LEMA']) else match_row.iloc[0]['SUBLEMA']
                            kata_baru.append(lemma_atau_sub + suffix)
                            diganti = True
                            break

            if not diganti:
                kata_baru.append(kata)

        hasil_ganti = " ".join(kata_baru)
        teks = teks.replace(f'"{kutipan}"', f'"{hasil_ganti}"')

    return teks

def ganti_halus_ke_loma_di_luar_kutipan(teks, df_kamus):
    # 1. Pisahkan bagian dalam dan luar kutip
    pola = r'"[^"]+"'
    potongan = re.split(pola, teks)
    kutipan = re.findall(pola, teks)

    hasil_final = []

    for i, bagian in enumerate(potongan):
        # 2. Proses bagian di luar kutipan
        kata_baru = []
        for kata in bagian.split():
            suffix = re.findall(r'[.,!?]$', kata)
            tanda_akhir = suffix[0] if suffix else ''
            kata_bersih = re.sub(r'[^\w-]', '', kata.lower())

            # Cek kata di kamus
            baris_kata = df_kamus[
                (df_kamus['LEMA'].str.lower() == kata_bersih) |
                (df_kamus['SUBLEMA'].str.lower() == kata_bersih)
            ]

            diganti = False
            if not baris_kata.empty:
                asal_tingkat = baris_kata.iloc[0]['(HALUS/LOMA/KASAR)']
                if pd.notna(asal_tingkat) and asal_tingkat.lower() in ['halus', 'halus/loma', 'loma/halus']:
                    sinonim_raw = baris_kata.iloc[0]['SINONIM'] if 'SINONIM' in baris_kata.columns else ""
                    if pd.notna(sinonim_raw):
                        sinonim_list = []
                        for frag in sinonim_raw.split(","):
                            sinonim_list += [s.strip().lower() for s in frag.split(".") if s.strip()]

                        # Cari sinonim dengan tingkat tutur LOMA
                        pengganti_ditemukan = False
                        for s in sinonim_list:
                            baris_sinonim = df_kamus[
                                ((df_kamus['LEMA'].str.lower() == s) | (df_kamus['SUBLEMA'].str.lower() == s)) &
                                (df_kamus['(HALUS/LOMA/KASAR)'].str.lower().isin(
                                    ['loma', 'loma/kasar', 'kasar/loma', 'loma/halus']
                                ))
                            ]
                            if not baris_sinonim.empty:
                                pengganti = baris_sinonim.iloc[0]['LEMA'] if pd.notna(baris_sinonim.iloc[0]['LEMA']) else baris_sinonim.iloc[0]['SUBLEMA']
                                kata_baru.append(pengganti + tanda_akhir)
                                diganti = True
                                pengganti_ditemukan = True
                                break

                        if not pengganti_ditemukan:
                            kata_baru.append(kata)  # Tidak ada sinonim cocok → biarkan
                            diganti = True

            if not diganti:
                kata_baru.append(kata)

        hasil_final.append(" ".join(kata_baru))

        # 3. Tambahkan kutipan jika ada
        if i < len(kutipan):
            hasil_final.append(kutipan[i])

    return "".join(hasil_final)

def ganti_klasifikasi_bahasa(teks, df_kamus, tingkat_tutur):
    if not tingkat_tutur:
        return teks  # Jika None atau kosong, kembalikan teks tanpa perubahan
    
    """
    Fungsi ini mengganti kata di luar kutipan berdasarkan tingkat_tutur:
    - 'Loma'  : ganti kata HALUS ke LOMA (jika ada sinonim LOMA).
    - 'Halus' : ganti kata LOMA ke HALUS (jika ada sinonim HALUS).
    Jika tidak ada sinonim yang cocok, kata dibold.
    """
    tingkat_tutur = tingkat_tutur.strip().lower()

    pola_kutipan = r'"[^"]+"'
    potongan = re.split(pola_kutipan, teks)
    kutipan = re.findall(pola_kutipan, teks)

    hasil_final = []

    for i, bagian in enumerate(potongan):
        kata_baru = []
        for kata in bagian.split():
            suffix = re.findall(r'[.,!?]$', kata)
            tanda_akhir = suffix[0] if suffix else ''
            kata_bersih = re.sub(r'<[^>]+>', '', kata)  # Hilangkan tag HTML
            kata_bersih = re.sub(r'[^\w-]', '', kata_bersih.lower())  # Bersihkan tanda baca

            baris_kata = df_kamus[
                (df_kamus['LEMA'].str.lower() == kata_bersih) |
                (df_kamus['SUBLEMA'].str.lower() == kata_bersih)
            ]

            if not baris_kata.empty:
                tingkat = str(baris_kata.iloc[0]['(HALUS/LOMA/KASAR)']).strip().lower()
                sinonim_raw = baris_kata.iloc[0]['SINONIM']
                
                if tingkat_tutur == 'loma':
                    target_filter = ['loma', 'halus/loma', 'loma/halus', 'loma/kasar']
                else:  # halus
                    target_filter = ['halus', 'halus/loma', 'loma/halus']

                # Cek apakah kata perlu diganti
                jika_harus_diganti = tingkat not in target_filter

                if jika_harus_diganti:
                    pengganti = None
                    if pd.notna(sinonim_raw):
                        sinonim_list = [s.strip().lower() for s in re.split(r'[.,]', sinonim_raw) if s.strip()]
                        for s in sinonim_list:
                            baris_sinonim = df_kamus[
                                ((df_kamus['LEMA'].str.lower() == s) | (df_kamus['SUBLEMA'].str.lower() == s)) &
                                (df_kamus['(HALUS/LOMA/KASAR)'].str.strip().str.lower().isin(target_filter))
                            ]
                            if not baris_sinonim.empty:
                                pengganti = baris_sinonim.iloc[0]['LEMA'] if pd.notna(baris_sinonim.iloc[0]['LEMA']) else baris_sinonim.iloc[0]['SUBLEMA']
                                break  # Ambil sinonim pertama yang cocok

                    if pengganti:
                        if kata[0].isupper():
                            pengganti = pengganti.capitalize()
                        kata_baru.append(pengganti + tanda_akhir)
                    else:
                        kata_baru.append(f"<b>{kata}</b>")
                else:
                    kata_baru.append(kata)
            else:
                kata_baru.append(kata)

        hasil_final.append(" ".join(kata_baru))

        if i < len(kutipan):
            hasil_final.append(kutipan[i])

    return "".join(hasil_final)

def ganti_klasifikasi_bahasa_preserve(teks, df_kamus, klasifikasi_bahasa_umum):
    if not klasifikasi_bahasa_umum:
        return teks

    # Siapkan kamus sementara dengan LEMA dan SUBLEMA yang dinormalisasi
    df_kamus_temp = df_kamus.copy()
    df_kamus_temp["LEMA_norm"] = df_kamus_temp["LEMA"].str.lower().apply(unidecode)
    df_kamus_temp["SUBLEMA_norm"] = df_kamus_temp["SUBLEMA"].str.lower().apply(unidecode)

    # Tokenisasi: kata, tanda baca, spasi, HTML
    tokens = re.findall(r'\w+|[^\w\s]|\s+|<[^>]+>', teks)

    hasil = []
    for token in tokens:
        if re.match(r'^\w+$', token):
            kata_asli = token
            kata_bersih = unidecode(kata_asli.lower())  # Normalisasi aksen

            baris_kata = df_kamus_temp[
                (df_kamus_temp['LEMA_norm'] == kata_bersih) |
                (df_kamus_temp['SUBLEMA_norm'] == kata_bersih)
            ]

            if baris_kata.empty:
                hasil.append(f"<i>{kata_asli}</i>")
                continue

            tingkat = str(baris_kata.iloc[0]['(HALUS/LOMA/KASAR)']).lower()
            sinonim_raw = baris_kata.iloc[0]['SINONIM']

            if klasifikasi_bahasa_umum.lower() == 'loma':
                target_filter = ['loma', 'halus/loma', 'loma/halus', 'loma/kasar']
            else:
                target_filter = ['halus', 'halus/loma', 'loma/halus']

            harus_diganti = not any(t in tingkat for t in target_filter)

            if harus_diganti:
                pengganti = None
                if pd.notna(sinonim_raw):
                    sinonim_list = [s.strip().lower() for s in re.split(r'[.,]', sinonim_raw) if s.strip()]
                    for s in sinonim_list:
                        s_norm = unidecode(s)
                        baris_sinonim = df_kamus_temp[
                            ((df_kamus_temp['LEMA_norm'] == s_norm) | (df_kamus_temp['SUBLEMA_norm'] == s_norm)) &
                            (df_kamus_temp['(HALUS/LOMA/KASAR)'].str.lower().isin(target_filter))
                        ]
                        if not baris_sinonim.empty:
                            pengganti = baris_sinonim.iloc[0]['LEMA'] if pd.notna(baris_sinonim.iloc[0]['LEMA']) else baris_sinonim.iloc[0]['SUBLEMA']
                            break

                if pengganti:
                    if kata_asli[0].isupper():
                        pengganti = pengganti.capitalize()
                    hasil.append(pengganti)
                else:
                    hasil.append(f"<b>{kata_asli}</b>")
            else:
                hasil.append(kata_asli)
        else:
            hasil.append(token)

    return ''.join(hasil)

def ganti_semua_ke_loma_preserve(teks, df_kamus):
    loma_list = ['loma', 'halus/loma', 'loma/halus', 'loma/kasar']

    tokens = re.findall(r'\w+|[^\w\s]|\s+|<[^>]+>', teks)
    hasil = []

    for token in tokens:
        if re.match(r'^\w+$', token):
            kata_asli = token
            kata_lower = kata_asli.lower()

            # 1. Cek di LEMA atau SUBLEMA (tanpa unidecode)
            baris_kata = df_kamus[
                (df_kamus['LEMA'].str.lower() == kata_lower) |
                (df_kamus['SUBLEMA'].str.lower() == kata_lower)
            ]

            # 2. Kalau tidak ketemu → cek perbedaan e vs é (pakai unidecode sementara)
            if baris_kata.empty:
                kata_unidecode = unidecode(kata_lower)
                baris_kata = df_kamus[
                    (df_kamus['LEMA'].str.lower().apply(unidecode) == kata_unidecode) |
                    (df_kamus['SUBLEMA'].str.lower().apply(unidecode) == kata_unidecode)
                ]

                # Jika ketemu dari e→é, sesuaikan kapitalisasi
                if not baris_kata.empty:
                    # ambil dulu dari LEMA, kalau kosong baru fallback ke SUBLEMA
                    if pd.notna(baris_kata.iloc[0]['LEMA']) and baris_kata.iloc[0]['LEMA'] != "":
                        pengganti_kamus = baris_kata.iloc[0]['LEMA']
                    else:
                        pengganti_kamus = baris_kata.iloc[0]['SUBLEMA']

                    # pastikan tidak NaN/kosong
                    if pd.notna(pengganti_kamus) and pengganti_kamus != "":
                        if kata_asli.isupper():
                            pengganti_kamus = pengganti_kamus.upper()
                        elif kata_asli[0].isupper():
                            pengganti_kamus = pengganti_kamus.capitalize()
                        hasil.append(pengganti_kamus)
                        continue  # langsung lanjut ke token berikutnya

            # 3. Kalau tetap kosong → italic & skip
            if baris_kata.empty:
                hasil.append(f"<i>{kata_asli}</i>")
                continue

            tingkat_tutur = str(baris_kata.iloc[0]['(HALUS/LOMA/KASAR)']).strip().lower()

            # 4. Kalau sudah termasuk loma_list → biarkan
            if tingkat_tutur in loma_list:
                hasil.append(kata_asli)
                continue

            # 5. Cari sinonim yang tingkat tutur-nya ada di loma_list
            sinonim_raw = baris_kata.iloc[0]['SINONIM']
            pengganti = None
            if pd.notna(sinonim_raw):
                sinonim_list = [s.strip() for s in re.split(r'[.,]', sinonim_raw) if s.strip()]
                for s in sinonim_list:
                    s_lower = s.lower()
                    baris_sinonim = df_kamus[
                        ((df_kamus['LEMA'].str.lower() == s_lower) |
                         (df_kamus['SUBLEMA'].str.lower() == s_lower)) &
                        (df_kamus['(HALUS/LOMA/KASAR)'].str.strip().str.lower().isin(loma_list))
                    ]
                    if not baris_sinonim.empty:
                        pengganti = baris_sinonim.iloc[0]['LEMA'] if pd.notna(baris_sinonim.iloc[0]['LEMA']) else baris_sinonim.iloc[0]['SUBLEMA']
                        break

            # 6. Output hasil
            if pengganti:
                if kata_asli.isupper():
                    pengganti = pengganti.upper()
                elif kata_asli[0].isupper():
                    pengganti = pengganti.capitalize()
                hasil.append(pengganti)
            else:
                hasil.append(f"<b>{kata_asli}</b>")
        else:
            hasil.append(token)

    return ''.join(hasil)

def ganti_semua_ke_halus_preserve(teks, df_kamus):
    loma_list = ['halus', 'halus/loma', 'loma/halus']

    tokens = re.findall(r'\w+|[^\w\s]|\s+|<[^>]+>', teks)
    hasil = []

    for token in tokens:
        if re.match(r'^\w+$', token):
            kata_asli = token
            kata_lower = kata_asli.lower()

            # 1. Cek di LEMA atau SUBLEMA (tanpa unidecode)
            baris_kata = df_kamus[
                (df_kamus['LEMA'].str.lower() == kata_lower) |
                (df_kamus['SUBLEMA'].str.lower() == kata_lower)
            ]

            # 2. Kalau tidak ketemu → cek perbedaan e vs é (pakai unidecode sementara)
            if baris_kata.empty:
                kata_unidecode = unidecode(kata_lower)
                baris_kata = df_kamus[
                    (df_kamus['LEMA'].str.lower().apply(unidecode) == kata_unidecode) |
                    (df_kamus['SUBLEMA'].str.lower().apply(unidecode) == kata_unidecode)
                ]

                # Jika ketemu dari e→é, sesuaikan kapitalisasi
                if not baris_kata.empty:
                    # ambil dulu dari LEMA, kalau kosong baru fallback ke SUBLEMA
                    if pd.notna(baris_kata.iloc[0]['LEMA']) and baris_kata.iloc[0]['LEMA'] != "":
                        pengganti_kamus = baris_kata.iloc[0]['LEMA']
                    else:
                        pengganti_kamus = baris_kata.iloc[0]['SUBLEMA']

                    # pastikan tidak NaN/kosong
                    if pd.notna(pengganti_kamus) and pengganti_kamus != "":
                        if kata_asli.isupper():
                            pengganti_kamus = pengganti_kamus.upper()
                        elif kata_asli[0].isupper():
                            pengganti_kamus = pengganti_kamus.capitalize()
                        hasil.append(pengganti_kamus)
                        continue

            # 3. Kalau tetap kosong → italic & skip
            if baris_kata.empty:
                hasil.append(f"<i>{kata_asli}</i>")
                continue

            tingkat_tutur = str(baris_kata.iloc[0]['(HALUS/LOMA/KASAR)']).strip().lower()

            # 4. Kalau sudah termasuk loma_list → biarkan
            if tingkat_tutur in loma_list:
                hasil.append(kata_asli)
                continue

            # 5. Cari sinonim yang tingkat tutur-nya ada di loma_list
            sinonim_raw = baris_kata.iloc[0]['SINONIM']
            pengganti = None
            if pd.notna(sinonim_raw):
                sinonim_list = [s.strip() for s in re.split(r'[.,]', sinonim_raw) if s.strip()]
                for s in sinonim_list:
                    s_lower = s.lower()
                    baris_sinonim = df_kamus[
                        ((df_kamus['LEMA'].str.lower() == s_lower) |
                         (df_kamus['SUBLEMA'].str.lower() == s_lower)) &
                        (df_kamus['(HALUS/LOMA/KASAR)'].str.strip().str.lower().isin(loma_list))
                    ]
                    if not baris_sinonim.empty:
                        pengganti = baris_sinonim.iloc[0]['LEMA'] if pd.notna(baris_sinonim.iloc[0]['LEMA']) else baris_sinonim.iloc[0]['SUBLEMA']
                        break

            # 6. Output hasil
            if pengganti:
                if kata_asli.isupper():
                    pengganti = pengganti.upper()
                elif kata_asli[0].isupper():
                    pengganti = pengganti.capitalize()
                hasil.append(pengganti)
            else:
                hasil.append(f"<b>{kata_asli}</b>")
        else:
            hasil.append(token)

    return ''.join(hasil)

# def ganti_kata_etimologi(teks, df_kamus):
#     # Tokenisasi kata & tanda baca
#     kata_token = re.findall(r"\w+|[^\w\s]", teks, re.UNICODE)
#     kata_ganti = {}

#     for i, token in enumerate(kata_token):
#         token_bersih = token.lower()

#         # Cari di kamus jika ETIMOLOGI-nya bukan 'sunda'
#         cocok = df_kamus[
#             ((df_kamus['LEMA'].str.lower() == token_bersih) |
#              (df_kamus['SUBLEMA'].str.lower() == token_bersih)) &
#             (~df_kamus['ETIMOLOGI'].str.lower().str.contains('sunda', na=False))
#         ]

#         if cocok.empty:
#             continue

#         # Ambil sinonim
#         sinonim_raw = cocok.iloc[0]['SINONIM']
#         if pd.isna(sinonim_raw):
#             continue

#         sinonim_list = [s.strip().lower() for s in re.split(r'[;,]', str(sinonim_raw)) if s.strip()]
#         ditemukan = None

#         # Urutan prioritas: cari yang ETIMOLOGI 'sunda', lalu 'indonesia'
#         for etimo_prioritas in ['sunda', 'indonesia']:
#             for sinonim in sinonim_list:
#                 baris_sinonim = df_kamus[
#                     ((df_kamus['LEMA'].str.lower() == sinonim) |
#                      (df_kamus['SUBLEMA'].str.lower() == sinonim)) &
#                     (df_kamus['ETIMOLOGI'].str.lower().str.contains(etimo_prioritas, na=False))
#                 ]
#                 if not baris_sinonim.empty:
#                     ditemukan = sinonim
#                     break
#             if ditemukan:
#                 break

#         if ditemukan:
#             kata_ganti[i] = ditemukan

#     # Rekonstruksi kalimat dengan mengganti token sesuai
#     hasil = []
#     for i, token in enumerate(kata_token):
#         if i in kata_ganti:
#             kata_baru = kata_ganti[i]
#             hasil.append(kata_baru.capitalize() if token.istitle() else kata_baru)
#         else:
#             hasil.append(token)

#     # Gabungkan kembali dengan spasi antar kata (kecuali tanda baca)
#     return ''.join([
#         token if re.fullmatch(r'\W', token) else ' ' + token
#         for token in hasil
#     ]).strip()
def ganti_kata_dengan_sinonim_dari_arti_ekuivalen(teks, df_kamus):
    hasil = []

    # Tokenisasi kata + tanda baca tetap dipisah
    tokens = re.findall(r'\w+|[^\w\s]', teks, re.UNICODE)

    for i, token in enumerate(tokens):
        # Cek apakah token adalah kata atau tanda baca
        if re.fullmatch(r'\w+', token):
            token_lc = token.lower()

            # Cari baris di kamus: LEMA atau SUBLEMA == token & EKUIVALEN == token
            cocok = df_kamus[
                ((df_kamus['LEMA'].str.lower() == token_lc) | 
                (df_kamus['SUBLEMA'].str.lower() == token_lc)) 
                &
                ((df_kamus['EKUIVALEN 1'].str.lower() == token_lc) | 
                (df_kamus['EKUIVALEN 2'].str.lower() == token_lc))
            ]

            if not cocok.empty:
                sinonim_raw = cocok.iloc[0]['SINONIM']
                if pd.isna(sinonim_raw):
                    hasil.append(token)
                    continue

                # Ambil daftar sinonim
                sinonim_list = [s.strip() for s in str(sinonim_raw).split(",") if s.strip()]
                if sinonim_list:
                    pengganti = random.choice(sinonim_list)
                    pengganti = pengganti.capitalize() if token.istitle() else pengganti
                    hasil.append(pengganti)
                else:
                    hasil.append(token)
            else:
                hasil.append(token)
        else:
            # Tanda baca langsung dimasukkan
            hasil.append(token)

    # Gabungkan ulang dengan aturan: spasi antar kata, tapi tidak di depan tanda baca
    final_teks = ''
    for i, token in enumerate(hasil):
        if i > 0 and re.fullmatch(r'\w+', token) and re.fullmatch(r'\w+', hasil[i - 1]):
            final_teks += ' '
        elif i > 0 and re.fullmatch(r'\w+', token) and re.fullmatch(r'[^\w\s]', hasil[i - 1]):
            final_teks += ' '
        final_teks += token

    return final_teks.strip()

def lema_arti_mirip(bot_response, df_kamus):
    def mirip_satu_huruf(a, b):
        return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85 or abs(len(a) - len(b)) <= 1
    
    tokens = re.findall(r'\w+|[^\w\s]', bot_response, re.UNICODE)
    hasil = []

    for token in tokens:
        # Lewati angka murni atau angka diikuti titik (nomor urut)
        if re.fullmatch(r'\d+\.?', token):
            hasil.append(token)
            continue
            
        if not re.fullmatch(r'\w+', token):  # tanda baca
            hasil.append(token)
            continue

        token_lc = token.lower()

        # 1. Cek di LEMA / SUBLEMA
        cocok = df_kamus[
            (df_kamus['LEMA'].str.lower() == token_lc) |
            (df_kamus['SUBLEMA'].str.lower() == token_lc)
        ]
        if not cocok.empty:
            arti_eq = (
                str(cocok.iloc[0]['EKUIVALEN 1'] or cocok.iloc[0]['EKUIVALEN 2'])
            ).lower()
            if arti_eq and (arti_eq == token_lc or mirip_satu_huruf(arti_eq, token_lc)):
                lemma_or_sub = cocok.iloc[0]['LEMA'] if pd.notna(cocok.iloc[0]['LEMA']) else cocok.iloc[0]['SUBLEMA']
                tingkat = str(cocok.iloc[0]['(HALUS/LOMA/KASAR)']).lower()

                # Kalau tingkat tutur sudah LOMA atau kombinasi → langsung pakai LEMA/SUBLEMA
                if any(x in tingkat for x in ['loma', 'loma/kasar', 'halus/loma']):
                    hasil.append(lemma_or_sub.capitalize() if token.istitle() else lemma_or_sub)
                    continue

                # Kalau bukan → cari sinonim yang LOMA
                sinonim_raw = cocok.iloc[0]['SINONIM']
                if pd.notna(sinonim_raw):
                    sinonim_list = [s.strip().lower() for s in str(sinonim_raw).split(",") if s.strip()]
                    sinonim_loma = df_kamus[
                        ((df_kamus['LEMA'].str.lower().isin(sinonim_list)) | 
                        (df_kamus['SUBLEMA'].str.lower().isin(sinonim_list))) &
                        (df_kamus['(HALUS/LOMA/KASAR)'].str.lower().isin(['loma', 'halus/loma', 'loma/kasar']))
                    ]

                    if not sinonim_loma.empty:
                        kata_sinonim = sinonim_loma.iloc[0]['LEMA'] if pd.notna(sinonim_loma.iloc[0]['LEMA']) else sinonim_loma.iloc[0]['SUBLEMA']
                        hasil.append(kata_sinonim.capitalize() if token.istitle() else kata_sinonim)
                        continue

                # Jika tidak ada sinonim LOMA → pakai LEMA/SUBLEMA asli
                hasil.append(lemma_or_sub.capitalize() if token.istitle() else lemma_or_sub)
                continue
            hasil.append(token)
            continue

        # 2. Jika tidak ada di LEMA/SUBLEMA, cek di EKUIVALEN
        cocok_eq = df_kamus[
            (df_kamus['EKUIVALEN 1'].fillna('').str.lower() == token_lc) |
            (df_kamus['EKUIVALEN 2'].fillna('').str.lower() == token_lc)
        ]
        if not cocok_eq.empty:
            pengganti = cocok_eq.iloc[0]['LEMA'] if pd.notna(cocok_eq.iloc[0]['LEMA']) else cocok_eq.iloc[0]['SUBLEMA']
            if pd.notna(pengganti):
                hasil.append(pengganti.capitalize() if token.istitle() else pengganti)
                continue

        # 3. Jika tidak ada semua → pakai kata asli
        hasil.append(token)

    # Gabungkan ulang
    kalimat_final = ''
    for i, token in enumerate(hasil):
        if i > 0:
            if re.fullmatch(r'\w+', token):  # Jika token adalah kata
                kalimat_final += ' ' + token
            elif re.fullmatch(r'[.,!?;:\'\"”]', token):  # Jika tanda baca: gabung langsung
                kalimat_final += token
            else:
                kalimat_final += ' ' + token
        else:
            kalimat_final += token

    return kalimat_final

def substitusi_dari_arti_ekuivalen(teks, df_kamus, tingkat_tutur):
    """
    Cari padanan kata italic dari ARTI EKUIVALEN dan ganti dengan kata dari LEMA/SUBLEMA.
    - 'loma'  : target 'LOMA', 'HALUS/LOMA', 'LOMA/HALUS', 'LOMA/KASAR'
    - 'halus' : target 'HALUS', 'HALUS/LOMA'
    Jika tidak ada yang sesuai target filter:
      1. Cari di kolom SINONIM → kata di LEMA/SUBLEMA sesuai target filter.
      2. Kalau tidak ada → bold kata dari LEMA/SUBLEMA.
    Kalau tidak ada di ARTI EKUIVALEN → jangan diubah (tetap <i>...</i>).
    """

    pola_italic = r"<i>(.*?)</i>"

    def ganti_kata_italic(match):
        inner_text = match.group(1)
        if not inner_text:  # kalau kosong, jangan diubah
            return match.group(0)

        kata = inner_text.strip().lower()

        # Cari di ARTI EKUIVALEN
        mask_eq = (
            df_kamus["EKUIVALEN 1"].fillna('').str.lower() == kata
        ) | (
            df_kamus["EKUIVALEN 2"].fillna('').str.lower() == kata
        )
        row_eq = df_kamus[mask_eq]
        if not row_eq.empty:
            # Target filter berdasar tingkat_tutur
            if tingkat_tutur.lower() == 'loma':
                target_filter = ['loma', 'halus/loma', 'loma/halus', 'loma/kasar']
            else:  # halus
                target_filter = ['halus', 'halus/loma']

            # Ambil tingkat tutur kata
            tingkat = str(row_eq.iloc[0]["(HALUS/LOMA/KASAR)"]).lower()

            # Fungsi untuk ambil kata pengganti
            def ambil_kata(row):
                return row["LEMA"] if pd.notna(row["LEMA"]) and str(row["LEMA"]).strip() else row["SUBLEMA"]

            # 1. Kalau baris ini sudah sesuai target
            if tingkat in target_filter:
                return ambil_kata(row_eq.iloc[0])

            # 2. Cari baris lain dengan ARTI EKUIVALEN sama & sesuai target
            candidates = df_kamus[
                (df_kamus["EKUIVALEN 1"].fillna('').str.lower() == kata) |
                (df_kamus["EKUIVALEN 2"].fillna('').str.lower() == kata)
            ]
            candidates = candidates[candidates["(HALUS/LOMA/KASAR)"].astype(str).str.lower().isin(target_filter)]
            if not candidates.empty:
                return ambil_kata(candidates.iloc[0])

            # 3. Cari di kolom SINONIM
            sinonim_raw = row_eq.iloc[0]["SINONIM"]
            if pd.notna(sinonim_raw):
                for s in [x.strip().lower() for x in sinonim_raw.split(",") if x.strip()]:
                    baris_sinonim = df_kamus[
                        ((df_kamus["LEMA"].str.lower() == s) | (df_kamus["SUBLEMA"].str.lower() == s)) &
                        (df_kamus["(HALUS/LOMA/KASAR)"].astype(str).str.lower().isin(target_filter))
                    ]
                    if not baris_sinonim.empty:
                        return ambil_kata(baris_sinonim.iloc[0])

            # 4. Tidak ada pengganti yang sesuai → bold kata dari LEMA/SUBLEMA
            return f"<b>{ambil_kata(row_eq.iloc[0])}</b>"

        # Tidak ketemu di ARTI EKUIVALEN → jangan diubah
        return match.group(0)

    teks_baru = re.sub(pola_italic, ganti_kata_italic, teks)
    teks_baru = re.sub(r'([.,!?])(?=\S)', r'\1 ', teks_baru)

    return teks_baru.strip()

# aturan valid sequence
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

# def terjemahkan_dengan_KS(teks_indo, df_kamus, df_majemuk):
#     """
#     Terjemahkan teks Indo → Sunda:
#     1. Cek frasa 2 kata di df_majemuk (EKUIVALEN → LEMA).
#     2. Kalau tidak ada, cek frasa 2 kata di df_kamus (EKUIVALEN 1 / 2 → LEMA/SUBLEMA).
#     3. Kalau tidak ada, cek per kata di df_kamus (dengan KLAS. + valid sequence).
#     4. Kalau tidak ada juga, pakai kata asal.
#     """
#     hasil = []
#     kelas_hasil = []
#     tokens = re.findall(r'\w+|\d+\.|[^\w\s]', teks_indo, re.UNICODE)
#     i = 0

#     while i < len(tokens):
#         kandidat_sunda = None
#         kandidat_klas = None

#         # === STEP 1 & 2: cek frasa 2 kata ===
#         if i + 1 < len(tokens):
#             dua_kata = f"{tokens[i]} {tokens[i+1]}".lower()

#             # cek di df_majemuk
#             cocok_maj = df_majemuk[df_majemuk["EKUIVALEN"].str.lower() == dua_kata]
#             if not cocok_maj.empty:
#                 lema = cocok_maj.iloc[0]["LEMA"]
#                 klas = cocok_maj.iloc[0].get("KLAS.", None)
#                 if cek_valid_urutan(kelas_hasil, klas, valid_sequence):
#                     kandidat_sunda, kandidat_klas = lema, klas
#             else:
#                 # cek di df_kamus (EKUIVALEN 1/2)
#                 cocok_dua = df_kamus[
#                     (df_kamus["EKUIVALEN 1"].str.lower() == dua_kata) |
#                     (df_kamus["EKUIVALEN 2"].str.lower() == dua_kata)
#                 ]
#                 if not cocok_dua.empty:
#                     for idx, row in cocok_dua.iterrows():
#                         lema = row["LEMA"] or row["SUBLEMA"]
#                         klas = row.get("KLAS.", None)
#                         if cek_valid_urutan(kelas_hasil, klas, valid_sequence):
#                             kandidat_sunda, kandidat_klas = lema, klas
#                             break

#             if kandidat_sunda:
#                 hasil.append(kandidat_sunda)
#                 kelas_hasil.append(kandidat_klas)
#                 i += 2
#                 continue

#         # === STEP 3: cek per kata ===
#         satu_kata = tokens[i].lower()
#         cocok_satu = df_kamus[
#             (df_kamus["EKUIVALEN 1"].str.lower() == satu_kata) |
#             (df_kamus["EKUIVALEN 2"].str.lower() == satu_kata)
#         ]

#         if not cocok_satu.empty:
#             for idx, row in cocok_satu.iterrows():
#                 lema = row["LEMA"] or row["SUBLEMA"]
#                 klas = row.get("KLAS.", None)
#                 if cek_valid_urutan(kelas_hasil, klas, valid_sequence):
#                     kandidat_sunda, kandidat_klas = lema, klas
#                     break

#             if kandidat_sunda:
#                 hasil.append(kandidat_sunda)
#                 kelas_hasil.append(kandidat_klas)
#             else:
#                 hasil.append(tokens[i])  # fallback
#                 kelas_hasil.append(None)
#         else:
#             hasil.append(tokens[i])  # fallback
#             kelas_hasil.append(None)

#         i += 1

#     # Gabungkan ulang
#     kalimat_akhir = ''
#     for j, token in enumerate(hasil):
#         if j > 0 and re.fullmatch(r'\w+', token) and re.fullmatch(r'\w+', hasil[j-1]):
#             kalimat_akhir += ' '
#         kalimat_akhir += token

#     return kalimat_akhir.strip()

def urai_awalan(kata):
    """
    Fungsi ini mengurai kata hasil imbuhan (misal: 'sublema') sehingga
    mengembalikan kata dasar (misal: 'lema').
    Pendekatan ini hanya menghapus awalan yang terdaftar.
    """

    # Daftar imbuhan awalan dalam bahasa Sunda (sesuai aturan yang kamu berikan)
    # Perlu diurutkan berdasarkan panjang agar yang panjang diperiksa dulu.
    imbuhan_awalan = [
        "pang", "mang", "nyang", "barang", "silih",
        "para", "pada", "ting", "pri", "per", "pra",  # imbuhan berbentuk lebih dari 2 huruf
        "pa", "pi", "sa", "si", "ti", "di", "ka", "nga", "ar"   # imbuhan dua huruf

    ]

    # Jika ada kasus khusus: misalnya apabila kata diawali "sub",
    # yang dalam contoh diinginkan mengembalikan kata dasar dengan menghapus "sub".
    if kata.startswith("sub"):
        return kata[3:]

    # Urutan pengecekan berdasarkan panjang imbuhan (dari yang terpanjang) agar tidak salah potong
    for imbuhan in sorted(imbuhan_awalan, key=len, reverse=True):
        if kata.startswith(imbuhan):
            return kata[len(imbuhan):]

    # Bila tidak ditemukan imbuhan, kembalikan kata aslinya
    return kata

def urai_akhiran(kata):
    """
    Fungsi ini mengurai kata hasil imbuhan akhiran (misal: 'ngendogan') sehingga
    mengembalikan kata dasar (misal: 'ngendog').
    Pendekatan ini hanya menghapus akhiran yang terdaftar.
    """

    # Daftar imbuhan akhiran dalam bahasa Sunda (rarangkén tukang)
    imbuhan_akhiran = ["keun", "eun", "ing", "na", "an"]  # urutkan dari yang terpanjang

    for imbuhan in sorted(imbuhan_akhiran, key=len, reverse=True):
        if kata.endswith(imbuhan):
            return kata[:-len(imbuhan)]

    # Bila tidak ditemukan imbuhan, kembalikan kata aslinya
    return kata

def urai_peleburan(kata):
    """
    Fungsi ini mengurai kata dengan awalan hasil peleburan berdasarkan aturan peluluhan awalan:
        - ng => k
        - ny => c atau s (mengembalikan 2 kemungkinan)
        - m => p
        - n => t (opsional)

    Jika ditemukan awalan 'ny', fungsi mengembalikan list 2 kata hasil peluluhan.
    """

    if len(kata) < 2:
        return [kata]

    hasil = []

    if kata.startswith("ng"):
        hasil.append("k" + kata[2:])
    elif kata.startswith("ny"):
        hasil.append("c" + kata[2:])  # kemungkinan 1
        hasil.append("s" + kata[2:])  # kemungkinan 2
    elif kata.startswith("m"):
        hasil.append("p" + kata[1:])
    elif kata.startswith("n"):
        hasil.append("t" + kata[1:])
    else:
        hasil.append(kata)

    return hasil

def urai_kata_sunda(kata):
    """
    Fungsi gabungan untuk mengurai awalan dan akhiran dari sebuah kata
    dalam Bahasa Sunda, mengembalikan bentuk dasar (lema) tanpa duplikat.
    """
    kata = bersihkan_teks(kata)
    kata = bersihkan_superscript(kata)

    # Uraikan awalan saja
    hasil_awalan = urai_awalan(kata)

    # Uraikan akhiran saja
    hasil_akhiran = urai_akhiran(kata)

    # Uraikan kombinasi awalan dan akhiran
    hasil_kombinasi = urai_akhiran(hasil_awalan)

    # Uraian Peleburan
    hasil_awal_lebur = urai_peleburan(kata)

    # Uraian kombinasi Peleburan dan akhiran
    hasil_kombinas_lebur_akhiran = list(map(urai_akhiran, hasil_awal_lebur))

    # Gabungkan dan hilangkan duplikat
    hasil_unik = list(set([hasil_awalan, hasil_akhiran, hasil_kombinasi] + hasil_awal_lebur + hasil_kombinas_lebur_akhiran))

    return {kata: hasil_unik}

def urai_kalimat_sunda(kalimat):
    """
    Fungsi ini menerima input berupa kalimat atau kumpulan kata dalam bahasa Sunda.
    Setiap kata akan diurai awalan dan akhirannya, lalu dikembalikan sebagai kamus
    berisi pasangan {kata_awal: [hasil_urai1, hasil_urai2, ...]}.
    """
    hasil = {}
    for kata in kalimat.split():
        hasil.update(urai_kata_sunda(kata))
    return hasil

def pengecekan_sublema(text, df_kamsus):    
    
    text = text.lower()
    hasil_urai = urai_kalimat_sunda(text)

    # Konversi kolom LEMA menjadi set
    lema_set = set(df_kamsus['LEMA'])
    
    # Ambil key jika salah satu valuenya ada di kolom LEMA
    hasil_keys = [key for key, values in hasil_urai.items() if any(val in lema_set for val in values)]
    
    return hasil_keys
 # ================= PENGURAIAN SUBLEMA =================

def constraint_text(text, df_kamus, df_idiom):

    list_hasil_penguraian_sublema = pengecekan_sublema(text, df_kamus)
    
    # ================= Clean text_kecil =================
    text = text.replace("-", " ")
    text_kecil_clean = re.sub(r"[^\w\s-]", "", text.lower())

    kata_kalimat = set(text_kecil_clean.split())

    # ================= Filter Kata di Kamus IDIOM & PARIBASA =================
    df_idiom["IDIOM"] = df_idiom["IDIOM"].str.lower().str.replace(";", ",", regex=False)
    df_idiom["IDIOM"] = df_idiom["IDIOM"].str.replace("é", "e")

    # Mengubah seluruh kolom menjadi satu list besar
    all_idioms = []
    for row in df_idiom["IDIOM"]:
        items = [i.strip() for i in row.split(",")]
        all_idioms.extend(items)

    def extract_idiom_words(kalimat_asli, word_list):
        kalimat_normal = kalimat_asli.replace("é", "e")

        words_asli = kalimat_asli.split()
        words_normal = kalimat_normal.split()
        result = []

        used_indices = set()

        # Cari idiom dari yang panjang ke pendek
        for length in [5, 4, 3, 2]:
            for i in range(len(words_normal) - length + 1):
                if any((i + j) in used_indices for j in range(length)):
                    continue  # Lewati jika bagian dari idiom sebelumnya

                sublist = " ".join(words_normal[i : i + length])
                if sublist in word_list:
                    result.extend(words_asli[i : i + length])
                    used_indices.update(range(i, i + length))

        return result

    # Panggil fungsi
    filtered_words_idiom = extract_idiom_words(text_kecil_clean, all_idioms)
    print(f"==========> {filtered_words_idiom}")

    # kata_kalimat = kata_kalimat - set(filtered_words_idiom)
    # print(f"==========> {kata_kalimat}")

    # ================= Filter Kata di Kamus LEMA=================

    df_e_petik = df_kamus[df_kamus["LEMA"].str.contains("[éÉ]", na=False, regex=True)]
    df_e_petik.loc[:, "LEMA"] = df_e_petik["LEMA"].str.replace("[éÉ]", "e", regex=True)
    kata_e_petik = {kata.lower() for kata in df_e_petik["LEMA"].astype(str)}

    # Ambil baris yang mengandung é atau É pada SUBLEMA
    df_e_petik_sub = df_kamus[
        df_kamus["SUBLEMA"].str.contains("[éÉ]", na=False, regex=True)
    ]
    df_e_petik_sub.loc[:, "SUBLEMA"] = df_e_petik_sub["SUBLEMA"].str.replace(
        "[éÉ]", "e", regex=True
    )
    kata_e_petik_sub = {
        item.strip().lower()
        for sublema in df_e_petik_sub["SUBLEMA"].dropna()
        for item in sublema.split(",")
    }

    df_e_petik2 = df_kamus[df_kamus["LEMA"].str.contains("[èÈ]", na=False, regex=True)]
    df_e_petik2.loc[:, "LEMA"] = df_e_petik2["LEMA"].str.replace(
        "[èÈ]", "e", regex=True
    )
    kata_e_petik2 = {kata.lower() for kata in df_e_petik2["LEMA"].astype(str)}

    kata_dataframe1 = {
        kata.lower() for kata in df_kamus["LEMA"].astype(str)
    }  # Konversi ke string jika ada NaN

    kata_dataframe2 = {
        kata.strip().replace(".", "")  # Hapus spasi ekstra & titik
        for kata_list in df_kamus["SUBLEMA"].astype(str)  # Konversi ke string
        for kata in kata_list.split(",")  # Pecah berdasarkan koma
        if kata.strip()  # Hanya tambahkan jika tidak kosong
    }

    # Ambil baris yang mengandung é atau É pada SUBLEMA
    df_e_petik_sub2 = df_kamus[
        df_kamus["SUBLEMA"].str.contains("[èÈ]", na=False, regex=True)
    ]
    df_e_petik_sub2.loc[:, "SUBLEMA"] = df_e_petik_sub2["SUBLEMA"].str.replace(
        "[èÈ]", "e", regex=True
    )
    kata_e_petik_sub2 = {
        item.strip().lower()
        for sublema in df_e_petik_sub2["SUBLEMA"].dropna()
        for item in sublema.split(",")
    }

    # Membersihkan teks: Menghapus tanda baca dan membuat huruf kecil
    def clean_text(text):
        text = re.sub(r"[^\w\s]", "", text)  # Hapus tanda baca
        return text.lower()  # Konversi ke huruf kecil

    kata_dataframe3 = {
        kata.strip().replace(".", "")  # Hapus spasi ekstra & titik
        for kata_list in df_kamus["SINONIM"].astype(str)  # Konversi ke string
        for kata in kata_list.split(",")  # Pecah berdasarkan koma
        if kata.strip()  # Hanya tambahkan jika tidak kosong
    }

    # Memisahkan setiap kata dalam set
    # kata_dataframe4 = {
    #     kata
    #     for kalimat in df_kamus["CONTOH KALIMAT LOMA"].astype(str)
    #     for kata in clean_text(kalimat).split()
    # }

    # kata_dataframe = kata_dataframe1 | kata_dataframe2 | kata_dataframe4

    kata_dataframe = (
        kata_dataframe1
        | kata_dataframe2
        | kata_dataframe3
        # | kata_dataframe4
        | kata_e_petik
        | kata_e_petik2
        # | nama_orang_tempat
        | kata_e_petik_sub
        | kata_e_petik_sub2
    )

    kata_terdapat = sorted(kata_kalimat.intersection(kata_dataframe))
    kata_terdapat = [kata for kata in kata_terdapat if not re.search(r"\d", kata)]
    kata_terdapat = kata_terdapat + filtered_words_idiom
    kata_terdapat = list(set(kata_terdapat + list_hasil_penguraian_sublema))

    kata_tidak_terdapat = sorted(kata_kalimat - kata_dataframe)
    kata_tidak_terdapat = [
        kata for kata in kata_tidak_terdapat if not re.search(r"\d", kata)
    ]
    kata_tidak_terdapat = [
        kata for kata in kata_tidak_terdapat if kata not in filtered_words_idiom
    ]
    kata_tidak_terdapat[:] = [item for item in kata_tidak_terdapat if item not in list_hasil_penguraian_sublema]

    print("\n")
    print("Kata yang ditemukan di Kamus:", kata_terdapat)
    print("Kata yang tidak ditemukan di Kamus:", kata_tidak_terdapat)

    # =====================================================================================
    # ======================== 9. Apakah ada sinonim Berjenis Loma? ========================
    # =====================================================================================

    # Dictionary untuk menyimpan pasangan kata asli dan kata pengganti
    pasangan_kata = {}
    kata_terdapat_tidak_loma = []

    # Loop setiap kata dalam kata_terdapat
    for kata in kata_terdapat[
        :
    ]:  # Gunakan slicing agar bisa mengubah list di dalam loop
        # Cari kata di kamus
        row = df_kamus[df_kamus["LEMA"].str.lower() == kata]

        if not row.empty:
            kategori = row["(HALUS/LOMA/KASAR)"].values[0]  # Ambil kategori kata utama

            if pd.notna(kategori) and "LOMA" not in kategori.upper():
                # Ambil daftar sinonim dari kolom SINONIM
                sinonim_raw = (
                    row["SINONIM"].values[0]
                    if pd.notna(row["SINONIM"].values[0])
                    else ""
                )
                sinonim_list = [s.strip() for s in sinonim_raw.split(",") if s.strip()]

                # Cari sinonim yang berkategori "LOMA"
                sinonim_loma = []
                for sinonim in sinonim_list:
                    sinonim_row = df_kamus[df_kamus["LEMA"].str.lower() == sinonim]
                    if not sinonim_row.empty:
                        kategori_sinonim = sinonim_row["(HALUS/LOMA/KASAR)"].values[0]
                        if kategori_sinonim == "LOMA":
                            sinonim_loma.append(sinonim)

                # Jika ada sinonim LOMA, pilih salah satu sebagai pengganti
                if sinonim_loma:
                    pasangan_kata[kata] = random.choice(sinonim_loma)
                else:
                    # Jika tidak ada sinonim LOMA, pindahkan ke kata_tidak_terdapat
                    kata_tidak_terdapat.append(kata)
                    kata_terdapat.remove(kata)  # Hapus dari kata_terdapat
                    kata_terdapat_tidak_loma.append(kata)

    # Tampilkan hasil pasangan kata
    for kata_asli, kata_pengganti in pasangan_kata.items():
        kata_terdapat.append(kata_pengganti)
        print(f"{kata_asli} -> {kata_pengganti}")

    print(pasangan_kata)

    # =====================================================================================
    # ================================ 10.Pengecekan Typo =================================
    # =====================================================================================

    return (
        kata_terdapat,
        kata_tidak_terdapat,
        kata_terdapat_tidak_loma,
        pasangan_kata,
        kata_e_petik,
        kata_e_petik2,
        kata_e_petik_sub,
        kata_e_petik_sub2,
        filtered_words_idiom,
    )


def highlight_text(translated_text, df_kamus, df_idiom, fitur, tingkat_tutur):
    translated_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", translated_text)
    (
        kata_terdapat,
        kata_tidak_terdapat,
        kata_terdapat_tidak_loma,
        pasangan_kata,
        kata_e_petik,
        kata_e_petik2,
        kata_e_petik_sub,
        kata_e_petik_sub2,
        filtered_words_idiom,
    ) = constraint_text(translated_text, df_kamus, df_idiom)

    hasil_lines = []
    pasangan_ekuivalen = {}

    for baris in translated_text.splitlines():
        kata_list = baris.split()
        hasil_baris = []

        i = 0
        while i < len(kata_list):
            match = re.match(r"^(\W*)([\w'-]+)(\W*)$", kata_list[i])
            if not match:
                matches = re.findall(r"\*([^\s*]+)\*", translated_text)
                if matches:
                    kata_list_clean = re.sub(r"[^a-zA-Z0-9\s]", "", kata_list[i])
                    if kata_list_clean not in kata_terdapat:
                        hasil_baris.append(
                            f'<i>{kata_list[i]}</i>'
                        )
                    else:
                        hasil_baris.append(kata_list[i])
                else:
                    hasil_baris.append(kata_list[i])
                i += 1
                continue

            simbol_depan, kata, simbol_belakang = match.groups()
            kata = pasangan_kata.get(kata.lower(), kata)

            if kata.lower() not in kata_terdapat:
                if kata.lower() not in kata_terdapat_tidak_loma:
                    if re.search(r"\d", kata):
                        hasil_baris.append(simbol_depan + kata + simbol_belakang)
                    else:
                        hasil_baris.append(
                            f'{simbol_depan}<i>{kata}</i>{simbol_belakang}'
                        )
                else:
                    if kata not in filtered_words_idiom and (fitur == "chatbot" or fitur == "terjemahindosunda"):
                        # print(f"==? ASD : {kata}")
                        mask = (df_kamus["LEMA"] == kata) | (df_kamus["SUBLEMA"] == kata)
                        ekuivalen = [
                            row["EKUIVALEN 1"] or row["EKUIVALEN 2"]
                            for _, row in df_kamus.loc[mask].iterrows()
                        ]
                        if (
                            len(ekuivalen) > 0 and not pd.isna(ekuivalen[0])
                            and str(ekuivalen[0]).lower() == kata.lower()
                        ):
                            # Check if ekuivalen is not empty 
                            print(f"EKUIVALEN ARRAY =========> {ekuivalen}")
                            # Pastikan ambil elemen pertama
                            ekuivalen = ekuivalen[0] if isinstance(ekuivalen, (list, np.ndarray)) else ekuivalen
                            ekuivalen = str(ekuivalen).split(',')[0]
                            pasangan_ekuivalen[kata] = ekuivalen
                            print(f"TYPE =========> {type(ekuivalen)}")                         
                            hasil_baris.append(
                                f'{simbol_depan}<span>{ekuivalen}</span>{simbol_belakang}'
                            )
                            print("ADA EKUIVALENNYA")
                        else:
                            ekuivalen = kata
                            hasil_baris.append(                               
                                f'{simbol_depan}<b>{ekuivalen}</b>{simbol_belakang}'
                            )                            
                            print("TIDAK ADA EKUIVALENNYA")

                        print(f"===========>>> {ekuivalen}")
                    else:
                        # print(f"==? XZY : {kata}")
                        hasil_baris.append(
                            f'{simbol_depan}<span>{kata}</span>{simbol_belakang}'
                        )
            else:
                kata_lower = kata.lower()
                # if kata_lower in kata_e_petik:
                #     kata = kata.replace("e", "é").replace("E", "É")
                # if kata_lower in kata_e_petik2:
                #     kata = kata.replace("e", "è").replace("E", "È")
                # if kata_lower in kata_e_petik_sub:
                #     kata = kata.replace("e", "è").replace("E", "È")
                # if kata_lower in kata_e_petik_sub2:
                #     kata = kata.replace("e", "è").replace("E", "È")
                hasil_baris.append(simbol_depan + kata + simbol_belakang)

            i += 1
        hasil_lines.append(" ".join(hasil_baris))
        teks_hasil = "<br>".join(hasil_lines)
        # Tambahkan spasi setelah tanda baca kalau belum ada
        teks_hasil = re.sub(r"([.,!?])(?=\S)", r"\1 ", teks_hasil)  # Titik/Koma/Tanya/Seru diikuti tanpa spasi
        # Opsional: tambahkan setelah kutipan
        teks_hasil = re.sub(r"([\"']) (?=\w)", r"\1 ", teks_hasil)
        teks_hasil = ganti_klasifikasi_bahasa(teks_hasil, df_kamus, tingkat_tutur)

    return teks_hasil, kata_terdapat, kata_tidak_terdapat, pasangan_kata, pasangan_ekuivalen


def ubah_ke_lema(chat_user_indo, df_kamus, df_idiom):
    (
        kata_terdapat,
        kata_tidak_terdapat,
        kata_terdapat_tidak_loma,
        pasangan_kata,
        kata_e_petik,
        kata_e_petik2,
        kata_e_petik_sub,
        kata_e_petik_sub2,
        filtered_words_idiom,
    ) = constraint_text(chat_user_indo, df_kamus, df_idiom)
    
    # Tokenisasi kalimat
    kata_kata = chat_user_indo.lower().split()

    # Buat mapping dari ARTI EKUIVALEN ke LEMA
    map_arti_ke_lema = {}
    
    for idx, row in df_kamus.iterrows():
        # Ambil arti ekuivalen atau gunakan arti 1 jika kosong
        arti_ekuivalen = row.fillna('')["EKUIVALEN 1"] or row.fillna('')["EKUIVALEN 2"]
        if pd.isna(arti_ekuivalen):
            arti_ekuivalen = row["ARTI 1"]
            
        lema = row["LEMA"]
        
        if pd.notna(arti_ekuivalen):
            for kata in str(arti_ekuivalen).split(","):
                map_arti_ke_lema[kata.strip().lower()] = lema

    # Proses kombinasi kata
    tokens = re.findall(r"\w+|[^\w\s]", chat_user_indo.lower())
    

    hasil = []
    pasangan_ganti = {}  # Dictionary untuk menyimpan pasangan kata yang diganti
    i = 0
    while i < len(tokens):
        token = tokens[i]
    
        # Hanya proses jika token termasuk dalam kata_tidak_terdapat
        if token in kata_tidak_terdapat:
            if re.match(r"[^\w\s]", token):
                hasil.append(token)
                i += 1
                continue
    
            trigram = " ".join(tokens[i : i + 3])
            bigram = " ".join(tokens[i : i + 2])
            unigram = token
    
            if i + 2 < len(tokens) and trigram in map_arti_ke_lema:
                hasil.append(map_arti_ke_lema[trigram])
                pasangan_ganti[trigram] = map_arti_ke_lema[trigram]
                i += 3
            elif i + 1 < len(tokens) and bigram in map_arti_ke_lema:
                hasil.append(map_arti_ke_lema[bigram])
                pasangan_ganti[bigram] = map_arti_ke_lema[bigram]
                i += 2
            elif unigram in map_arti_ke_lema:
                hasil.append(map_arti_ke_lema[unigram])
                pasangan_ganti[unigram] = map_arti_ke_lema[unigram]
                i += 1
            else:
                hasil.append(unigram)
                i += 1
        else:
            hasil.append(token)
            i += 1  # ⬅️ WAJIB untuk menghindari infinite loop
    
        hasil_akhir = (
            # " ".join(hasil)
            " ".join(str(item) for item in hasil)
            .replace(" ,", ",")
            .replace(" .", ".")
            .replace(" ?", "?")
            .replace(" !", "!")
        )

    return hasil_akhir, pasangan_ganti

def find_the_lema_pair(data_kamus, kata_list, kata_tidak_terdapat):
    cols_lower = ['EKUIVALEN 1', 'EKUIVALEN 2', 'ARTI 1']
    data_kamus[cols_lower] = data_kamus[cols_lower].apply(lambda col: col.fillna('').str.lower())
    # Normalisasi kolom SUBLEMA jadi list, ganti "é" menjadi "e"
    def sublema_contains_kata(sublema_str, kata):
        if pd.isna(sublema_str):
            return False
        # Ganti semua "é" dengan "e" pada sublema_str
        sublema_str = sublema_str.replace('é', 'e')
        return kata in [item.strip() for item in sublema_str.split(',')]

    # Membuat dictionary hasil
    hasil_dict = {}

    # Ganti semua "é" dengan "e" pada kata_list
    kata_list = [kata.replace('é', 'e') for kata in kata_list]
    
    import re
    
    def bersihkan_kata(kata_list):
        bersih_list = []
        for kata in kata_list:
            # Hanya mempertahankan huruf (termasuk huruf dengan aksen seperti é)
            bersih = re.sub(r"[^\w\s]|_", "", kata, flags=re.UNICODE)
            # Optional: jika ingin menghapus angka juga, gunakan ini:
            # bersih = re.sub(r"[^\p{L}\s]", "", kata)
            bersih_list.append(bersih)
        return bersih_list
    
    # Contoh penggunaan
    hasil = bersihkan_kata(kata_list)
    print(hasil)

    # Cari di kolom LEMA
    for kata in kata_list:
        if kata in kata_tidak_terdapat:  # Hanya proses jika ada di list1
            arti_lema = data_kamus[data_kamus['LEMA'].str.replace('é', 'e') == kata]['ARTI 1'].tolist()
            if arti_lema:
                hasil_dict[kata] = arti_lema[0]
            else:    
                arti_lema_ekuivalen = [
                    row['EKUIVALEN 1'] or row['EKUIVALEN 2']
                    for _, row in data_kamus[data_kamus['LEMA'].str.replace('é', 'e') == kata].fillna('').iterrows()
                ]
                if arti_lema_ekuivalen:           
                    hasil_dict[kata] = arti_lema_ekuivalen
    
    # Cari di kolom SUBLEMA
    for kata in kata_list:
        if kata in kata_tidak_terdapat and kata not in hasil_dict:  # Tambahkan cek list1
            match_rows = data_kamus[data_kamus['SUBLEMA'].apply(lambda x: sublema_contains_kata(x, kata))]
            for _, row in match_rows.iterrows():
                if row['ARTI 1'] is None or pd.isna(row['ARTI 1']):
                    hasil_dict[kata] = (row['EKUIVALEN 1'] or row['EKUIVALEN 2']) if pd.notna(row['EKUIVALEN 1']) or pd.notna(row['EKUIVALEN 2']) else None
                else:
                    hasil_dict[kata] = row['ARTI 1']
                break  # Ambil arti pertama yang ditemukan


    # Tampilkan hasil dalam bentuk dict
    print(hasil_dict)
    return hasil_dict

def cari_arti_lema(teks, df):
    """
    Mencari arti berdasarkan LEMA dan SUBLEMA dari teks, dengan normalisasi huruf é menjadi e.

    Parameters:
    - teks (str): Teks yang ingin dianalisis.
    - df (pd.DataFrame): DataFrame dengan kolom 'LEMA', 'SUBLEMA', dan 'ARTI 1'.

    Returns:
    - dict: Pasangan {kata_dari_teks: arti} yang ditemukan dari teks.
    """
    # Ganti é dengan e di teks
    teks = teks.lower().replace('é', 'e')
    kata_dalam_teks = teks.split()

    # Ganti é dengan e di kolom LEMA dan SUBLEMA
    df = df.copy()
    df['LEMA'] = df['LEMA'].str.lower().str.replace('é', 'e')
    df['SUBLEMA'] = df['SUBLEMA'].fillna('').str.lower().str.replace('é', 'e')

    hasil = {}

    for kata in kata_dalam_teks:
        # Cek ke kolom LEMA
        cocok_lema = df[df['LEMA'] == kata]
        if not cocok_lema.empty:
            arti = cocok_lema.iloc[0]['ARTI 1']
            hasil[kata] = arti
            continue

        # Cek ke kolom SUBLEMA
        for _, baris in df.iterrows():
            sublema_list = [s.strip() for s in baris['SUBLEMA'].split(',')]
            if kata in sublema_list:
                hasil[kata] = baris['ARTI 1']
                break

    return hasil
