
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from textwrap import dedent
from datetime import date, datetime
from io import BytesIO
import os

st.set_page_config(page_title="Dépenses - Gestion", page_icon="💸", layout="centered")

ARTICLES_XLSX_DEFAULT = Path("grocerie.xlsx")
PURCHASES_CSV = Path("purchases.csv")
SETTINGS_CSV = Path("settings.csv")
DATE_FMT = "%Y-%m-%d"

@st.cache_data(show_spinner=False)
def load_articles(xlsx_path: str):
    try:
        df = pd.read_excel(xlsx_path)
    except Exception:
        return pd.DataFrame(columns=["Article", "Catégorie", "Sous-catégorie", "Prix_unitaire"])
    df.columns = [str(c).strip() for c in df.columns]
    col_article = next((c for c in df.columns if c.lower() in ["article", "produit", "item", "designation", "désignation", "name"]), df.columns[0])
    col_cat = next((c for c in df.columns if c.lower() in ["categorie", "catégorie", "category", "famille", "groupe"]), None)
    col_subcat = next((c for c in df.columns if "sous" in c.lower() and "cat" in c.lower()), None)
    col_price = next((c for c in df.columns if c.lower() in ["prix", "prix_unitaire", "pu", "price", "unit_price", "tarif", "cost"]), None)
    out = pd.DataFrame()
    out["Article"] = df[col_article].astype(str).str.strip()
    out["Catégorie"] = df[col_cat].astype(str).str.strip() if col_cat else "Non classé"
    out["Sous-catégorie"] = df[col_subcat].astype(str).str.strip() if col_subcat else ""
    out["Prix_unitaire"] = pd.to_numeric(df[col_price], errors="coerce") if col_price else np.nan
    out = out[out["Article"].str.len() > 0].dropna(subset=["Article"])
    return out.drop_duplicates(subset=["Article"]).reset_index(drop=True)

@st.cache_data(show_spinner=False)
def read_purchases():
    if PURCHASES_CSV.exists():
        return pd.read_csv(PURCHASES_CSV, parse_dates=["Date"])
    return pd.DataFrame(columns=["Date", "Article", "Catégorie", "Sous-catégorie", "Quantité", "Prix_unitaire", "Total"])

def save_purchases(df: pd.DataFrame):
    df.to_csv(PURCHASES_CSV, index=False)

st.title("💸 Gestion des Dépenses")
articles_df = load_articles(str(ARTICLES_XLSX_DEFAULT))
purchases_df = read_purchases()

st.subheader("🛒 Enregistrer un achat")
with st.form("add_form"):
    d = st.date_input("Date", value=date.today())
    art = st.selectbox("Article", options=articles_df["Article"].unique())
    if art:
        possible_cats = sorted(articles_df["Catégorie"].dropna().unique())
        cat = st.selectbox("Catégorie", options=possible_cats)
        possible_subcats = sorted(articles_df.loc[articles_df["Catégorie"] == cat, "Sous-catégorie"].dropna().unique())
        if possible_subcats and any(s != "" for s in possible_subcats):
            subcat = st.selectbox("Sous-catégorie", options=possible_subcats)
        else:
            subcat = ""
        qty = st.number_input("Quantité", min_value=0.0, step=1.0, value=1.0)
        suggested_price = float(articles_df.loc[articles_df["Article"] == art, "Prix_unitaire"].dropna().iloc[0]) if not articles_df.loc[articles_df["Article"] == art, "Prix_unitaire"].dropna().empty else 0.0
        unit_price = st.number_input("Prix unitaire (MAD)", min_value=0.0, step=0.1, value=suggested_price)
        total = qty * unit_price
        st.write(f"**Total : {total:,.2f} MAD**")
        if st.form_submit_button("➕ Ajouter l'achat"):
            new_row = pd.DataFrame([{
                "Date": pd.to_datetime(d),
                "Article": art,
                "Catégorie": cat,
                "Sous-catégorie": subcat,
                "Quantité": qty,
                "Prix_unitaire": unit_price,
                "Total": total
            }])
            purchases_df = pd.concat([purchases_df, new_row], ignore_index=True)
            save_purchases(purchases_df)
            st.success("Achat ajouté ✅")

st.subheader("📋 Historique")
if not purchases_df.empty:
    st.dataframe(purchases_df, use_container_width=True)
