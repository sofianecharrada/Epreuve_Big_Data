import streamlit as st
import pandas as pd

st.set_page_config(page_title="FreshPoint - Pilotage Exploitation", layout="wide")

st.title("❄️ FreshPoint - Tableau de Bord Décisionnel")
st.sidebar.header("Filtres de Périmètre")
ville = st.sidebar.selectbox("Ville", ["Toutes", "Lyon", "Nantes", "Lille"])
date_selection = st.sidebar.date_input("Date d'analyse")

st.markdown("---")

col1, col2, col3 = st.columns(3)
col1.metric("Paniers Non Servis (Retraits Manqués)", "14", "-2 vs hier")
col2.metric("Respect Contrat GlacioTrans", "94.2%", "Seuil cible : 95%")[cite: 1]
col3.metric("Paniers en Alerte Froid (> 6°C)", "3", "À rembourser")[cite: 1]

st.subheader("📋 Bulletin matinal d'Inès (Généré à 6 h 30)")[cite: 1]
st.info("Consignes prioritaires à contrôler ce matin (basé sur les anomalies de télémétrie et retraits manqués de la veille) :")

bulletin_data = {
    "Consigne ID": ["LYON-04", "NANTES-02", "LILLE-09"],
    "Ville": ["Lyon", "Nantes", "Lille"],
    "Motif du contrôle": ["Température > 6°C pendant > 30 min", "Taux élevé de retraits manqués", "Compresseur lot défectueux"],
    "Action requise": ["Vérifier groupe froid / technicien", "Vérifier ouverture casiers application", "Remplacement préventif"]
}
st.table(pd.DataFrame(bulletin_data))