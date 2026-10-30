# Journaux

L’onglet **Journaux** présente les diagnostics réels du service. Il complète **Historique**, qui reste le journal des décisions et commandes.

## Consultation

- Actualisation automatique toutes les trois secondes tant que l’onglet est visible. La pause gèle l’affichage, même lorsqu’une requête est en cours, sans interrompre la collecte.
- Recherche littérale, insensible à la casse Unicode, dans le message ; filtres de niveau et de zones combinables. Les accents restent significatifs.
- Le niveau choisi est un seuil : ERROR inclut FATAL et ERROR ; DEBUG inclut tous les niveaux sauf TRACE. TRACE inclut tout.
- Sélection de plusieurs zones, toutes les zones ou aucune ; fermeture par Échap ou clic à l’extérieur.
- Lignes les plus récentes en bas. Le défilement suit les nouvelles lignes uniquement si le lecteur se trouve déjà en bas.
- Chargement des lignes précédentes par lots de 500. La fenêtre de rendu contient au plus 2 000 lignes et peut parcourir les archives en évacuant les lignes les plus récentes. La reprise revient à une fenêtre cohérente des dernières lignes.
- Téléchargement TXT des lignes conservées correspondant aux filtres, jusqu’à 10 000 lignes, indépendamment de la fenêtre affichée. Horodatages UTC dans le fichier et fuseau de l’installation dans l’interface.

## Collecte et zones

- `system` : démarrage/arrêt du service.
- `http` : requêtes en erreur, code HTTP, erreurs internes (classe d’erreur, sans corps de requête ni paramètres d’URL).
- `ocpp:<identifiant>` : connexion/refus/déconnexion, requêtes et réponses OCPP, erreurs et délais des appels. DEBUG pour les commandes ; TRACE pour MeterValues/Heartbeat. Mesures numériques, phases, unités et statuts autorisés uniquement ; les trames brutes et idTags ne sont jamais recopiés.
- `ha` : connexion WebSocket, lectures et erreurs HTTP/réseau. Succès de lecture limités à une ligne par dix secondes.
- `peugeot` : lectures de véhicules et de télémétrie, renouvellement d’accès, erreurs HTTP et codes fournisseur ; aucun VIN ni réponse OAuth.
- `ariston:<appareil>` : température, consigne, état, erreurs cloud et résultat des commandes natives.
- `site` : puissance réseau/solaire, courants et limites par phase, au plus toutes les dix secondes, en TRACE.
- `device:<appareil>` et `decisions` : événements existants et résumés des états/décisions, sans changer leur stockage historique.

Il ne s’agit pas d’une lecture du socket Docker ni d’une réexposition des traces brutes des bibliothèques tierces. Les lignes antérieures à l’installation de cette fonctionnalité et les sorties Docker précédentes ne peuvent pas être reconstituées.

## Persistance et confidentialité

La table additive `diagnostic_logs` est créée dans `app.db` (schéma SQLite 3), dans le volume `/data` existant. Configuration, sessions de charge, secrets chiffrés et événements sont conservés. Les sauvegardes SQLite incluent les journaux. Le journal est limité à **10 000 entrées** et **sept jours** ; le plafond atteint en premier s’applique. Les entrées expirées ne sont plus retournées et sont purgées à l’écriture suivante. Les lignes font au plus 4 000 caractères.

Le masque de secrets s’applique **avant l’écriture** : valeurs du coffre chiffré et jetons transitoires connus, champs d’authentification, mots de passe, Bearer/Basic, identifiants dans les URL et champs idTag/VIN. Les interfaces réseau produisent des résumés sélectionnés, jamais les corps HTTP/OAuth ni les trames OCPP entières. L’API et le téléchargement exigent la session administrateur habituelle et désactivent le cache.

Une défaillance de stockage du diagnostic ne fait pas échouer une commande : écritures au mieux, attente SQLite limitée à 50 ms, compteur de lignes perdues affiché. La console signale les interruptions, conserve les lignes déjà reçues et annonce les trous dus à la rétention.

API : `GET /api/v1/logs` et `GET /api/v1/logs/export`, paramètres `level`, `area` répété, `search` ; liste : `after` ou `before`, `limit` de 1 à 500. L’export ne prend pas le curseur de l’écran afin de couvrir toute la sélection retenue.
