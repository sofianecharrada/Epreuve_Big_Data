import os
import json
import glob
import pandas as pd
import duckdb

DATA_DIR = "FreshPoint_E05_data"
QUARANTINE_DIR = "quarantine"
os.makedirs(QUARANTINE_DIR, exist_ok=True)

def run_etl():
    print("=== Démarrage du pipeline ETL FreshPoint ===")
    
    # 1. Chargement des Référentiels
    consignes_df = pd.read_csv(os.path.join(DATA_DIR, "referentiels/consignes.csv"))
    casiers_df = pd.read_csv(os.path.join(DATA_DIR, "referentiels/casiers.csv"))
    contrat_df = pd.read_json(os.path.join(DATA_DIR, "referentiels/contrat.json"), typ='series')
    
    # 2. Ingestion et Normalisation des Commandes
    cmd_files = glob.glob(os.path.join(DATA_DIR, "commandes/*.csv"))
    cmd_list = [pd.read_csv(f) for f in cmd_files]
    commandes_df = pd.concat(cmd_list, ignore_index=True) if cmd_list else pd.DataFrame()
    
    # Traitement RGPD : Pseudonymisation (suppression des données identifiantes clients)
    if 'client_id' in commandes_df.columns:
        commandes_df['client_id_anonyme'] = commandes_df['client_id'].apply(lambda x: hash(str(x)))
    for col_to_drop in ['nom', 'courriel', 'telephone', 'client_nom']:
        if col_to_drop in commandes_df.columns:
            commandes_df = commandes_df.drop(columns=[col_to_drop])
            
    # 3. Règles de Qualité et Quarantaine
    # Règle 1 : Montant de commande positif
    invalid_amount = commandes_df[commandes_df['montant'] <= 0] if 'montant' in commandes_df.columns else pd.DataFrame()
    valid_commandes = commandes_df[commandes_df['montant'] > 0] if 'montant' in commandes_df.columns else commandes_df
    
    if not invalid_amount.empty:
        invalid_amount['motif_rejet'] = "Montant négatif ou nul"
        invalid_amount.to_csv(os.path.join(QUARANTINE_DIR, "commandes_rejetees.csv"), index=False)
    
    # 4. Ingestion des Dépôts Prestataire (GlacioTrans)
    depots_files = glob.glob(os.path.join(DATA_DIR, "depots_prestataire/*.csv"))
    depots_list = [pd.read_csv(f) for f in depots_files]
    depots_df = pd.concat(depots_list, ignore_index=True) if depots_list else pd.DataFrame()
    
    # Anonymisation des chauffeurs
    if 'chauffeur' in depots_df.columns:
        depots_df = depots_df.drop(columns=['chauffeur'])
        
    # 5. Ingestion de la Télémétrie & Chaîne du Froid
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
    
    # Connexion DuckDB pour les agrégations Gold
    con = duckdb.connect(database=':memory:')
    con.register("commandes", valid_commandes)
    con.register("depots", depots_df)
    con.register("consignes", consignes_df)
    
    if not telemetrie_df.empty and 'temperature' in telemetrie_df.columns:
        con.register("telemetrie", telemetrie_df)
        # Règle Chaîne du froid : Température > 6°C
        ruptures_froid = con.execute("""
            SELECT consigne_id, timestamp, temperature 
            FROM telemetrie 
            WHERE temperature > 6.0
        """).df()
        con.register("ruptures_froid", ruptures_froid)
    
    print("ETL exécuté avec succès. Tables prêtes pour l'analyse.")

if __name__ == "__main__":
    run_etl()