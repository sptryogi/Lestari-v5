import pandas as pd
import re

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

def load_kamus_dan_idiom():
    # Load kamus utama
    df_kamus = pd.read_excel("dataset/dataset_pure_KS21082025.xlsx")

    # Normalisasi teks ke lowercase
    df_kamus[['EKUIVALEN 1', 'EKUIVALEN 2', 'ARTI 1']] = df_kamus[
        ['EKUIVALEN 1', 'EKUIVALEN 2', 'ARTI 1']
    ].apply(lambda col: col.str.lower())

    # Bersihkan kamus & superscript
    df_kamus = bersihkan_kamus(df_kamus)
    df_kamus["LEMA"] = df_kamus["LEMA"].fillna("").astype(str).apply(bersihkan_superscript)
    df_kamus["SUBLEMA"] = df_kamus["SUBLEMA"].fillna("").astype(str).apply(bersihkan_superscript)

    # Dataset tambahan
    df_idiom = pd.read_excel("dataset/data_idiom (3).xlsx")
    df_majemuk = pd.read_excel("dataset/DAFTAR KATA MAJEMUK-FRASA.xlsx")
    df_pemendekan = pd.read_excel("dataset/PEMENDEKAN-Lema.xlsx")
    df_kosakata = pd.read_excel("dataset/KOSAKATA-FRASA-(Belajar-Guru).xlsx")

    return df_kamus, df_idiom, df_pemendekan, df_kosakata, df_majemuk