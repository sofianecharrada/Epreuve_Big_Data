import os
import json
import glob
import pandas as pd
import duckdb

# Récupère le dossier racine du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "FreshPoint_E05_data")
QUARANTINE_DIR = os.path.join(BASE_DIR, "quarantine")

os.makedirs(QUARANTINE_DIR, exist_ok=True)

def run_etl():
    print(f"=== [PARTIE 1] Démarrage du pipeline ETL FreshPoint ===")
    
    # ---------------------------------------------------------
    # 1. CHARGEMENT DES RÉFÉRENTIELS
    # ---------------------------------------------------------
    print("-> Chargement des référentiels...")
    path_consignes = os.path.join(DATA_DIR, "referentiels/consignes.csv")
    consignes_df = pd.read_csv(path_consignes) if os.path.exists(path_consignes) else pd.DataFrame()

    # ---------------------------------------------------------
    # 2. INGESTION ET NORMALISATION DES COMMANDES
    # ---------------------------------------------------------
    print("-> Ingestion et traitement des commandes...")
    cmd_path = os.path.join(DATA_DIR, "commandes/*.csv")
    cmd_files = glob.glob(cmd_path)
    
    if cmd_files:
        commandes_df = pd.concat([pd.read_csv(f) for f in cmd_files], ignore_index=True)
    else:
        commandes_df = pd.DataFrame()
    
    if not commandes_df.empty:
        total_lignes_cmd = len(commandes_df)
        
        # Déduplication sur clé métier si présente
        if 'commande_id' in commandes_df.columns:
            commandes_df = commandes_df.drop_duplicates(subset=['commande_id'])
        
        # Traitement RGPD : Pseudonymisation et Minimisation
        if 'client_id' in commandes_df.columns:
            commandes_df['client_id_anonyme'] = commandes_df['client_id'].apply(lambda x: hash(str(x)))
        
        cols_to_drop = ['nom', 'courriel', 'telephone', 'client_nom', 'client_prenom']
        for col in cols_to_drop:
            if col in commandes_df.columns:
                commandes_df = commandes_df.drop(columns=[col])

        # Règle de qualité : Montant de commande négatif ou nul
        invalid_mask = commandes_df['montant'] <= 0 if 'montant' in commandes_df.columns else pd.Series([False]*len(commandes_df))
        lignes_rejetees_cmd = invalid_mask.sum()
        
        q_path = os.path.join(QUARANTINE_DIR, "commandes_quarantaine.csv")
        
        if lignes_rejetees_cmd > 0:
            quarantine_cmd = commandes_df[invalid_mask].copy()
            quarantine_cmd['motif_rejet'] = "Règle bloquante: Montant de commande négatif ou nul"
            quarantine_cmd.to_csv(q_path, index=False)
            print(f"   [QUARANTINE] {lignes_rejetees_cmd} lignes rejetées.")
        else:
            if os.path.exists(q_path):
                os.remove(q_path)
            print("   [QUARANTINE] Aucune commande rejetée. Fichier nettoyé.")
        
        taux_rejet_cmd = (lignes_rejetees_cmd / total_lignes_cmd) * 100 if total_lignes_cmd > 0 else 0
        print(f"   [QUALITÉ COMMANDES] Total: {total_lignes_cmd} | Rejetées: {lignes_rejetees_cmd} | Taux de rejet: {taux_rejet_cmd:.2f}%")
        
        commandes_df = commandes_df[~invalid_mask]
    else:
        print("[ATTENTION] Aucune commande trouvée.")

    print("=== Fin de l'ETL (Partie 1) ===")
    return commandes_df

if __name__ == "__main__":
    run_etl()