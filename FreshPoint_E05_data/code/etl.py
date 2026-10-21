import os
import json
import glob
import pandas as pd
import duckdb

DATA_DIR = "FreshPoint_E05_data"
QUARANTINE_DIR = "quarantine"
os.makedirs(QUARANTINE_DIR, exist_ok=True)

def run_etl():
    print("=== [PARTIE 1] Démarrage du pipeline ETL FreshPoint ===")
    
    # ---------------------------------------------------------
    # 1. CHARGEMENT DES RÉFÉRENTIELS
    # ---------------------------------------------------------
    print("-> Chargement des référentiels (consignes, casiers)...")
    path_consignes = os.path.join(DATA_DIR, "referentiels/consignes.csv")
    path_casiers = os.path.join(DATA_DIR, "referentiels/casiers.csv")
    
    consignes_df = pd.read_csv(path_consignes) if os.path.exists(path_consignes) else pd.DataFrame()
    casiers_df = pd.read_csv(path_casiers) if os.path.exists(path_casiers) else pd.DataFrame()

    # ---------------------------------------------------------
    # 2. INGESTION ET NORMALISATION DES COMMANDES
    # ---------------------------------------------------------
    print("-> Ingestion et traitement des commandes...")
    cmd_files = glob.glob(os.path.join(DATA_DIR, "commandes/*.csv"))
    commandes_df = pd.concat([pd.read_csv(f) for f in cmd_files], ignore_index=True) if cmd_files else pd.DataFrame()
    
    if not commandes_df.empty:
        # Déduplication sur clé métier (ex: commande_id si présent, ou combinaison unique)
        if 'commande_id' in commandes_df.columns:
            commandes_df = commandes_df.drop_duplicates(subset=['commande_id'])
        
        # Traitement RGPD : Pseudonymisation et Minimisation
        if 'client_id' in commandes_df.columns:
            commandes_df['client_id_anonyme'] = commandes_df['client_id'].apply(lambda x: hash(str(x)))
        
        # Suppression stricte des données identifiantes
        cols_to_drop = ['nom', 'courriel', 'telephone', 'client_nom', 'client_prenom']
        for col in cols_to_drop:
            if col in commandes_df.columns:
                commandes_df = commandes_df.drop(columns=[col])

        # Règles de Qualité & Quarantaine (Seuils chiffrés)
        # Règle bloquante : Montant négatif ou nul
        invalid_mask = commandes_df['montant'] <= 0 if 'montant' in commandes_df.columns else pd.Series([False]*len(commandes_df))
        if invalid_mask.any():
            quarantine_cmd = commandes_df[invalid_mask].copy()
            quarantine_cmd['motif_rejet'] = "Règle bloquante: Montant de commande négatif ou nul"
            quarantine_cmd.to_csv(os.path.join(QUARANTINE_DIR, "commandes_quarantaine.csv"), index=False)
            print(f"   [QUARANTINE] {invalid_mask.sum()} commandes rejetées (montant invalide).")
        
        commandes_df = commandes_df[~invalid_mask]

    # ---------------------------------------------------------
    # 3. INGESTION DES DÉPÔTS PRESTATAIRE (GLACIOTRANS)
    # ---------------------------------------------------------
    print("-> Ingestion des dépôts prestataire (GlacioTrans)...")
    depots_files = glob.glob(os.path.join(DATA_DIR, "depots_prestataire/*.csv"))
    depots_df = pd.concat([pd.read_csv(f) for f in depots_files], ignore_index=True) if depots_files else pd.DataFrame()
    
    if not depots_df.empty:
        # Minimisation RGPD : Suppression du nom du chauffeur
        if 'chauffeur' in depots_df.columns:
            depots_df = depots_df.drop(columns=['chauffeur'])

    # ---------------------------------------------------------
    # 4. INGESTION DES RETRAITS APPLICATION (RETRAITS MANQUÉS)
    # ---------------------------------------------------------
    print("-> Ingestion des tentatives de retraits application...")
    retrait_files = glob.glob(os.path.join(DATA_DIR, "retraits_app/*.jsonl"))
    retraits_data = []
    for f in retrait_files:
        with open(f, 'r', encoding='utf-8') as file:
            for line in file:
                try:
                    retraits_data.append(json.loads(line.strip()))
                except:
                    pass
    retraits_df = pd.DataFrame(retraits_data) if retraits_data else pd.DataFrame()

    # ---------------------------------------------------------
    # 5. INGESTION DE LA TÉLÉMÉTRIE (CHAÎNE DU FROID)
    # ---------------------------------------------------------
    print("-> Ingestion de la télémétrie des consignes...")
    tel_files = glob.glob(os.path.join(DATA_DIR, "telemetrie/*.jsonl.gz"))
    tel_data = []
    for f in tel_files:
        with open(f, 'rb') as file:
            for line in file:
                try:
                    tel_data.append(json.loads(line.decode('utf-8')))
                except:
                    pass
    telemetrie_df = pd.DataFrame(tel_data) if tel_data else pd.DataFrame()

    # Contrôle de qualité télémétrie (Règle informative : température hors plage physique [-30, 40])
    if not telemetrie_df.empty and 'temperature' in telemetrie_df.columns:
        invalid_temp = (telemetrie_df['temperature'] < -30) | (telemetrie_df['temperature'] > 40)
        if invalid_temp.any():
            q_tel = telemetrie_df[invalid_temp].copy()
            q_tel['motif_rejet'] = "Règle informative: Température hors limites physiques"
            q_tel.to_csv(os.path.join(QUARANTINE_DIR, "telemetrie_quarantaine.csv"), index=False)
            print(f"   [QUARANTINE] {invalid_temp.sum()} mesures de télémétrie aberrantes isolées.")
        telemetrie_df = telemetrie_df[~invalid_temp]

    # ---------------------------------------------------------
    # 6. STRUCTURATION DES TABLES D'INDICATEURS (COUCHE GOLD - DUCKDB)
    # ---------------------------------------------------------
    print("-> Génération des tables d'indicateurs via DuckDB...")
    con = duckdb.connect(database=':memory:')
    
    if not commandes_df.empty:
        con.register("commandes", commandes_df)
    if not depots_df.empty:
        con.register("depots", depots_df)
    if not telemetrie_df.empty:
        con.register("telemetrie", telemetrie_df)
    if not consignes_df.empty:
        con.register("consignes", consignes_df)

    # Indicateur 1 : Ruptures de la chaîne du froid (> 6°C)
    if not telemetrie_df.empty and 'temperature' in telemetrie_df.columns:
        froid_table = con.execute("""
            SELECT consigne_id, COUNT(*) as nb_mesures_alerte
            FROM telemetrie
            WHERE temperature > 6.0
            GROUP BY consigne_id
        """).df()
        con.register("ind_chaine_froid", froid_table)

    # Indicateur 2 : Respect des livraisons GlacioTrans (Dépôts après 16h30)
    if not depots_df.empty and 'timestamp' in depots_df.columns:
        glacio_table = con.execute("""
            SELECT 
                DATE(timestamp) as date_depot,
                COUNT(*) as total_depots,
                SUM(CASE WHEN CAST(strftime('%H%M', timestamp) AS INT) > 1630 THEN 1 ELSE 0 END) as depots_tardifs
            FROM depots
            GROUP BY DATE(timestamp)
        """).df()
        con.register("ind_glaciotrans", glacio_table)

    print("=== ETL et modélisation de la Partie 1 terminés avec succès ===")
    return con

if __name__ == "__main__":
    run_etl()