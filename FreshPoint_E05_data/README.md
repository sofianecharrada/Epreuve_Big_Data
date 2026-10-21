# FreshPoint – données de l'épreuve E05 (version B)

Les données sont remises telles qu'elles sortent des systèmes : aucun nettoyage n'a été fait.
Période d'historique : du 1er septembre au 11 octobre 2026. Les journées du 12 et du 13 octobre sont dans `depots_quotidiens/`.

| Dossier | Format | Contenu |
|---|---|---|
| `commandes/` | CSV, un fichier par jour de retrait (+ un fichier de rattrapage) | Commandes de paniers : client, consigne, casier, créneau, montant, statut, horodatages |
| `telemetrie/` | JSON Lines compressé (.gz), un fichier par jour | État des consignes toutes les 10 minutes : température, porte, compresseur, firmware |
| `retraits_app/` | JSON Lines, un fichier par jour | Tentatives de retrait faites dans l'application et leur résultat |
| `depots_prestataire/` | CSV, un fichier par jour | Export du portail de GlacioTrans : dépôt des paniers dans les consignes, statut déclaré |
| `maintenance/` | JSON, un fichier par semaine | Tickets d'intervention technique sur les consignes |
| `meteo/` | JSON, un fichier par jour | Météo quotidienne par ville |
| `referentiels/` | CSV et JSON | Consignes (dont lot de compresseur), casiers, clients, contrat de GlacioTrans, codes de résultat |
| `depots_quotidiens/<jour>/` | mêmes formats | Dépôt de la journée du 12 octobre, puis de celle du 13 octobre (partie 2) |

Conventions connues :
- Les horodatages de `commandes/` et de `depots_prestataire/` (heures) sont en heure locale de France (Europe/Paris).
- Les autres horodatages sont indiqués avec leur fuseau quand il est explicite dans le fichier.
- `referentiels/contrat.json` donne les seuils et pénalités du contrat. Les codes de `retraits_app/` sont décrits dans `codes_resultat.json`.
- Aucune garantie de conformité : validez ce que vous lisez.
