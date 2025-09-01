
from flask import Blueprint, render_template, request
import pandas as pd
import unicodedata, re
from functools import lru_cache

sundalex_bp = Blueprint("sundalex", __name__)

def normalisasi_kata(kata):
    if kata is None:
        return ""
    kata = unicodedata.normalize('NFKD', str(kata)).encode('ASCII','ignore').decode('utf-8')
    kata = kata.lower()
    kata = re.sub(r'\d+$', '', kata)
    return kata.strip()

@lru_cache(maxsize=1)
def load_kamus():
    # sesuaikan path dataset Anda
    df = pd.read_excel("dataset/dataset_pure_KS21082025.xlsx")
    df["LEMA_NORM"] = df["LEMA"].fillna("").apply(normalisasi_kata)
    df["SUBLEMA_NORM"] = df["SUBLEMA"].fillna("").apply(normalisasi_kata)
    return df

@sundalex_bp.route("/sundalex", methods=["GET", "POST"])
def sundalex_view():
    results = None
    q = ""
    if request.method == "POST":
        q = request.form.get("q","")
        kata_norm = normalisasi_kata(q)
        df = load_kamus()
        cocok = df[(df["LEMA_NORM"] == kata_norm) | (df["SUBLEMA_NORM"] == kata_norm)]
        if not cocok.empty:
            results = cocok[['LEMA','SUBLEMA','(HALUS/LOMA/KASAR)','KLAS.','EKUIVALEN 1','EKUIVALEN 2','ARTI 1','SINONIM']].to_dict(orient="records")
        else:
            results = []
    return render_template("sundalex.html", q=q, results=results)
