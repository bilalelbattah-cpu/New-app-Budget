
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
import os

st.set_page_config(page_title="Dépenses - Gestion", page_icon="💸", layout="centered")

# ----------------------
# Helpers & constants
# ----------------------
DATA_DIR = Path(".")
ARTICLES_XLSX_DEFAULT = Path("grocerie.xlsx")
PURCHASES_CSV = Path("purchases.csv")
SETTINGS_CSV = Path("settings.csv")  # to store monthly budget target
DATE_FMT = "%Y-%m-%d"

# ----------------------
# Styles (mobile-friendly)
# ----------------------
st.markdown(
    '''
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    .stButton>button { width: 100%; border-radius: 12px; padding: .6rem 1rem; font-weight: 600; }
    .stSelectbox, .stTextInput, .stNumberInput, .stDateInput { border-radius: 12px; }
    .metric-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: .6rem; }
    @media (max-width: 640px) { .metric-row { grid-template-columns: 1fr; } }
    </style>
    ''',
    unsafe_allow_html=True
)

# ----------------------
# Load articles list from Excel
# ----------------------
@st.cache_data(show_spinner=False)
def load_articles(xlsx_path: str):
    try:
        df = pd.read_excel(xlsx_path)
    except Exception as e:
        st.warning("Impossible de lire le fichier des articles. Assure-toi qu'il s'appelle 'grocerie.xlsx' et qu'il est au même endroit que l'application.")
        return pd.DataFrame(columns=["Article", "Catégorie", "Prix_unitaire"])

    # Try to normalize column names
    df.columns = [str(c).strip() for c in df.columns]

    # Heuristics to map columns
    col_article = None
    for c in df.columns:
        if c.lower() in ["article", "produit", "item", "designation", "désignation", "name"]:
            col_article = c
            break
    if col_article is None:
        # fallback to first column
        col_article = df.columns[0]

    col_cat = None
    for c in df.columns:
        if c.lower() in ["categorie", "catégorie", "category", "famille", "groupe"]:
            col_cat = c
            break

    col_price = None
    for c in df.columns:
        if c.lower() in ["prix", "prix_unitaire", "pu", "price", "unit_price", "tarif", "cost"]:
            col_price = c
            break

    out = pd.DataFrame()
    out["Article"] = df[col_article].astype(str).str.strip()
    out["Catégorie"] = df[col_cat].astype(str).str.strip() if col_cat else "Non classé"
    out["Prix_unitaire"] = pd.to_numeric(df[col_price], errors="coerce") if col_price else np.nan

    # Drop empty rows
    out = out[out["Article"].str.len() > 0].dropna(subset=["Article"])
    out = out.drop_duplicates(subset=["Article"]).reset_index(drop=True)
    return out

@st.cache_data(show_spinner=False)
def read_purchases():
    if PURCHASES_CSV.exists():
        df = pd.read_csv(PURCHASES_CSV, parse_dates=["Date"])
        # Normalize types
        if "Total" not in df.columns:
            df["Total"] = df["Quantité"] * df["Prix_unitaire"]
        return df
    return pd.DataFrame(columns=["Date", "Article", "Catégorie", "Quantité", "Prix_unitaire", "Total"])

def save_purchases(df: pd.DataFrame):
    df.to_csv(PURCHASES_CSV, index=False)

def read_settings():
    if SETTINGS_CSV.exists():
        return pd.read_csv(SETTINGS_CSV)
    return pd.DataFrame([{"Mois": date.today().strftime("%Y-%m"), "Budget_mensuel": 0.0}])

def save_settings(df: pd.DataFrame):
    df.to_csv(SETTINGS_CSV, index=False)

# ----------------------
# Sidebar (Budget, import articles)
# ----------------------
st.sidebar.header("⚙️ Paramètres")
uploaded = st.sidebar.file_uploader("Importer un fichier d'articles (.xlsx)", type=["xlsx"], help="Optionnel si le fichier 'grocerie.xlsx' est déjà présent.")
if uploaded:
    with open(ARTICLES_XLSX_DEFAULT, "wb") as f:
        f.write(uploaded.getbuffer())
    st.sidebar.success("Fichier 'grocerie.xlsx' mis à jour.")

settings_df = read_settings()
current_month = date.today().strftime("%Y-%m")
# Ensure current month exists in settings
if current_month not in settings_df["Mois"].values:
    settings_df = pd.concat([settings_df, pd.DataFrame([{"Mois": current_month, "Budget_mensuel": 0.0}])], ignore_index=True)

sel_row = settings_df.index[settings_df["Mois"] == current_month][0]
budget_value = float(settings_df.loc[sel_row, "Budget_mensuel"])

new_budget = st.sidebar.number_input("Budget mensuel (MAD)", min_value=0.0, value=float(budget_value), step=50.0)
if st.sidebar.button("💾 Enregistrer le budget"):
    settings_df.loc[sel_row, "Budget_mensuel"] = new_budget
    save_settings(settings_df)
    st.sidebar.success("Budget enregistré.")

# ----------------------
# Header
# ----------------------
st.title("💸 Gestion des Dépenses")
st.caption("Ajoute tes achats, corrige les erreurs, et suis ton budget et tes synthèses mensuelles.")

# Load data
articles_df = load_articles(str(ARTICLES_XLSX_DEFAULT))
purchases_df = read_purchases()

# ----------------------
# Metrics
# ----------------------
# Compute month filter
def month_key(dt):
    return dt.strftime("%Y-%m")
if not purchases_df.empty:
    purchases_df["Mois"] = purchases_df["Date"].dt.strftime("%Y-%m")
else:
    purchases_df["Mois"] = pd.Series(dtype=str)

month_spent = float(purchases_df.loc[purchases_df["Mois"] == current_month, "Total"].sum()) if not purchases_df.empty else 0.0
budget = float(new_budget)
remaining = budget - month_spent

col1, col2, col3 = st.columns(3)
col1.metric("Dépenses du mois", f"{month_spent:,.2f} MAD")
col2.metric("Budget du mois", f"{budget:,.2f} MAD")
col3.metric("Reste", f"{remaining:,.2f} MAD", delta=f"{-month_spent:,.2f} MAD" if budget == 0 else None)

# ----------------------
# Add purchase form
# ----------------------
st.subheader("🛒 Enregistrer un achat")
with st.form("add_form", border=True):
    d = st.date_input("Date", value=date.today())
    art = st.selectbox("Article", options=articles_df["Article"].tolist() if not articles_df.empty else [], index=0 if not articles_df.empty else None, placeholder="Choisir un article")
    if art == "" or art is None:
        st.info("⚠️ Aucun article chargé. Ajoute/importe 'grocerie.xlsx' via la barre latérale.")
    cat_default = "Non classé"
    if not articles_df.empty:
        cat_default = str(articles_df.loc[articles_df["Article"] == art, "Catégorie"].iloc[0]) if (articles_df["Article"] == art).any() else "Non classé"
    cat = st.text_input("Catégorie", value=cat_default)
    qty = st.number_input("Quantité", min_value=0.0, step=1.0, value=1.0)
    # Suggest unit price if present
    suggested_price = float(articles_df.loc[articles_df["Article"] == art, "Prix_unitaire"].iloc[0]) if (not articles_df.empty and (articles_df["Article"] == art).any() and pd.notna(articles_df.loc[articles_df["Article"] == art, "Prix_unitaire"].iloc[0])) else 0.0
    unit_price = st.number_input("Prix unitaire (MAD)", min_value=0.0, step=0.1, value=suggested_price)
    total = qty * unit_price
    st.write(f"**Total : {total:,.2f} MAD**")

    submitted = st.form_submit_button("➕ Ajouter l'achat")
    if submitted:
        if art is None or art == "":
            st.error("Sélectionne un article.")
        else:
            new_row = pd.DataFrame([{
                "Date": pd.to_datetime(d),
                "Article": art,
                "Catégorie": cat if cat else "Non classé",
                "Quantité": float(qty),
                "Prix_unitaire": float(unit_price),
                "Total": float(total)
            }])
            purchases_df = pd.concat([purchases_df, new_row], ignore_index=True)
            save_purchases(purchases_df)
            st.success("Achat ajouté ✅")

# ----------------------
# Purchases table + delete
# ----------------------
st.subheader("📋 Historique des achats")
if purchases_df.empty:
    st.info("Aucun achat pour le moment.")
else:
    # Filter by month
    months = sorted(purchases_df["Mois"].unique(), reverse=True)
    sel_month = st.selectbox("Filtrer par mois", options=months, index=0 if current_month in months else 0)
    view_df = purchases_df[purchases_df["Mois"] == sel_month].copy()
    view_df_display = view_df.copy()
    view_df_display["Date"] = view_df_display["Date"].dt.strftime(DATE_FMT)

    st.dataframe(view_df_display[["Date","Article","Catégorie","Quantité","Prix_unitaire","Total"]], use_container_width=True)

    # Delete by selecting a row
    if not view_df.empty:
        # Build display labels
        opts = [f"{r.Date.strftime(DATE_FMT)} • {r.Article} • {r.Quantité:g}×{r.Prix_unitaire:g} = {r.Total:g} MAD" for r in view_df.itertuples(index=True)]
        to_delete = st.selectbox("Sélectionner un achat à supprimer", options=["—"] + opts, index=0)
        if to_delete != "—":
            if st.button("🗑️ Supprimer l'achat sélectionné", type="secondary"):
                # Identify the global index to drop
                idx_local = opts.index(to_delete)
                row = view_df.iloc[idx_local:idx_local+1]
                # Drop by matching unique combination (Date, Article, Quantité, Prix_unitaire, Total) within the full df
                mask = (
                    (purchases_df["Date"] == row["Date"].values[0]) &
                    (purchases_df["Article"] == row["Article"].values[0]) &
                    (purchases_df["Quantité"] == row["Quantité"].values[0]) &
                    (purchases_df["Prix_unitaire"] == row["Prix_unitaire"].values[0]) &
                    (purchases_df["Total"] == row["Total"].values[0])
                )
                purchases_df = purchases_df.loc[~mask].copy()
                save_purchases(purchases_df)
                st.success("Achat supprimé ✅")

    # Export
    st.download_button(
        "⬇️ Exporter les achats (CSV)",
        data=purchases_df.to_csv(index=False).encode("utf-8"),
        file_name="achats_export.csv",
        mime="text/csv",
        use_container_width=True
    )

# ----------------------
# Monthly summaries
# ----------------------
st.subheader("📆 Synthèse mensuelle")
if purchases_df.empty:
    st.info("Ajoute des achats pour voir la synthèse.")
else:
    smonths = sorted(purchases_df["Mois"].unique())
    m = st.selectbox("Choisir un mois", options=smonths, index=smonths.index(current_month) if current_month in smonths else len(smonths)-1)
    mdf = purchases_df[purchases_df["Mois"] == m].copy()

    total_m = float(mdf["Total"].sum())
    st.metric("Total du mois", f"{total_m:,.2f} MAD")

    by_cat = mdf.groupby("Catégorie", as_index=False)["Total"].sum().sort_values("Total", ascending=False)
    by_art = mdf.groupby("Article", as_index=False)["Total"].sum().sort_values("Total", ascending=False)

    colA, colB = st.columns(2)
    with colA:
        st.write("Dépenses par **catégorie**")
        st.bar_chart(by_cat.set_index("Catégorie"))
    with colB:
        st.write("Top **articles**")
        st.bar_chart(by_art.set_index("Article"))

    # Budget gauge-like info
    st.progress(min(1.0, (total_m / budget) if budget > 0 else 0.0), text=f"Progression budget: {total_m:,.2f} / {budget:,.2f} MAD")

    # Download monthly report
    def to_excel_bytes(dfs: dict):
        with pd.ExcelWriter(BytesIO(), engine="xlsxwriter") as writer:
            for name, df in dfs.items():
                df.to_excel(writer, sheet_name=name, index=False)
            writer._save()
            return writer.path.getvalue()

    report_data = {
        "Achats_mois": mdf.sort_values("Date"),
        "Par_catégorie": by_cat,
        "Par_article": by_art
    }
    xls_bytes = to_excel_bytes(report_data)
    st.download_button("📑 Exporter la synthèse (Excel)", data=xls_bytes, file_name=f"synthese_{m}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# ----------------------
# Tips for mobile
# ----------------------
st.markdown("---")
st.markdown("**Astuce mobile :** après déploiement sur Streamlit Cloud, ouvre l'URL sur ton smartphone et utilise **Ajouter à l'écran d'accueil** pour un accès rapide.")

st.caption("Fichier des articles attendu : **grocerie.xlsx** (colonnes recommandées : Article, Catégorie, Prix_unitaire).")
