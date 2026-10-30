# Sessions de charge

La rubrique **Sessions de charge** est indépendante du journal **Historique**, qui conserve les décisions et commandes. Elle utilise les compteurs réels du `ChargingTracker` de Solar Energy Manager, sans requête vers un serveur EVCC ni source d'historique concurrente.

## Consultation

- **Mois / Année / Total**, flèches de navigation et libellés français. Les dates utilisent le fuseau configuré pour l'installation, et non celui du navigateur.
- **Énergie** : histogramme empilé, réseau gris, solaire vert. Une origine non déterminable est représentée séparément. **Coût** : montants connus, avec indication des coûts partiels, et courbe du prix moyen pondéré sur un second axe lorsqu'il est calculable. Le CO₂ n'est pas proposé car aucun compteur fiable de CO₂ n'est actuellement collecté.
- Regroupement solaire/réseau, par point de charge ou par véhicule. Les couleurs utilisent tous les équipements connus pour rester cohérentes quand on filtre ou change de période.
- Filtres véhicule/borne, tri des colonnes, 25 lignes par page, totaux de toute la sélection. Sur téléphone : date, noms regroupés et deux colonnes au choix (**Chargé**, **Coût**, **Part solaire**, **Durée**). Sélectionner la même mesure dans l'autre colonne les permute ; un coût absent reste un tiret.
- Un clic sur la date ouvre le détail. Les champs indisponibles ne sont pas inventés. La durée de branchement est distincte de la durée de charge observée. Une durée interrompue par une perte de télémétrie est indiquée partielle.
- Exports CSV UTF-8 et Excel `.xlsx` de toute la sélection, sans limite à la page affichée. Les noms et libellés sont protégés contre les formules de tableur. Aucune bibliothèque de tableur supplémentaire n'est nécessaire.

## Persistance et mises à jour

Migration additive SQLite vers `user_version=2`, table `charging_history` dans le même `/data/app.db`. Le volume Docker et la clé de chiffrement restent identiques. Un checkpoint écrit l'état de comptage courant et l'historique dans une seule transaction SQLite ; un UUID identifie chaque branchement. Pauses/reprises et nouvelles transactions OCPP pendant le même branchement conservent cet UUID historique. Les corrections terminales mettent à jour ce même enregistrement.

La migration récupère la dernière session encore présente pour chaque borne dans les versions précédentes. Les sessions déjà remplacées avant cette version ont été perdues par l'ancien stockage : il est impossible de les recréer honnêtement. Aucun exemple ou jeu de données fictif n'est injecté dans l'application. Les données d'exemple sont limitées au serveur temporaire de tests `scripts/e2e_server.py`, dont le runtime matériel est désactivé.

Une perte de connexion du contrôleur ne ferme jamais une session. Un arrêt de Docker ne crée pas de nouvelle session. Un débranchement réellement observé termine la session, et le branchement suivant en ouvre une autre. Des changements physiques entièrement survenus pendant une absence totale de télémétrie ne peuvent pas être reconstruits avec certitude. Une correction de compteur reçue sans identité de transaction exploitable reste indisponible, plutôt que d'être attribuée à un autre véhicule.

Un relevé OCPP `StopTransaction` arrivant après `Available` est accepté uniquement pour la même identité de transaction, sur une borne toujours débranchée et sans nouvelle transaction. Il ne remet pas la borne dans un état de charge. Les gardes de commande et limites d'intensité existantes restent inchangées.

Les sessions vides sont conservées en interne. Par défaut, seules les sessions terminées dont le zéro est réellement mesuré et confirmé sont masquées ; le filtre **Inclure les sessions sans énergie** les rend visibles. Une session sans compteur ou sans index terminal confirmé reste visible et partielle.

## Conventions de calcul

Comme les graphiques de sessions EVCC étudiés, la session entière est affectée à sa **date de début**. Une recharge qui traverse minuit ne se scinde pas et n'est pas comptée dans deux mois. Ce graphique est un historique de sessions, pas la courbe quotidienne d'un compteur domestique.

L'énergie est la somme des différences de compteur valides ; les retours à zéro et écarts incohérents restent signalés. Les énergies solaires/réseau proviennent de l'allocation déjà intégrée par SEM sur chaque intervalle de compteur, à partir du mélange production PV/import réseau du logement. Il s'agit d'une estimation de provenance, et non d'un sous-compteur solaire dédié à la voiture. L'export est soustrait de la production locale utilisée. Aucun suivi de provenance de batterie domestique n'existe : aucune énergie de batterie n'est ajoutée artificiellement au PV.

Si la répartition de toute l'énergie est connue : `solaire = Σ énergie_session × part_solaire_session / 100`, `réseau = total − solaire`, `part_solaire = 100 × solaire / total`. En présence de lacunes, les quantités solaires/réseau connues sont conservées ; le reste demeure **origine inconnue** et le pourcentage complet n'est pas affiché. Les divisions par zéro produisent une valeur indisponible.

Le coût suit les tarifs intégrés au moment des mesures, et non le tarif actuel appliqué rétroactivement. Le graphique, le tableau et le total affiché utilisent tous les montants connus, y compris partiels, avec le qualificatif **partiel** lorsque la couverture est incomplète. Le prix moyen utilise uniquement les sessions entièrement mesurées et tarifées : `Σ coût complet / Σ énergie correspondante`. Son axe et sa courbe restent masqués si aucune moyenne fiable n'est disponible. Les tarifs nuls ou négatifs sont valides. Une journée avec uniquement des sessions non tarifées est indisponible, tandis qu'une journée vide peut afficher zéro. Dans l'API, `known_cost_eur` et `known_cost_count` exposent cette couverture connue ; `cost_eur`, `priced_count` et `priced_energy_kwh` conservent leur sens de sous-ensemble complet.

Le pourcentage de batterie au début est figé séparément du niveau courant. Il est capturé avant toute énergie chargée observée, sans préfixe de charge manquant ; les relevés Peugeot suivants actualisent uniquement le niveau courant/final. Au premier démarrage de 0.1.21, les départs enregistrés par 0.1.20 sans provenance sont réparés depuis la référence initiale persistante de l'estimateur lorsqu'elle est ancrée à zéro énergie et sans préfixe manquant. Si cette preuve n'existe plus, **Non enregistrée** remplace la valeur ambiguë. Aucun pourcentage initial n'est reconstruit par soustraction d'énergie au niveau final. Cette réparation conserve les affectations manuelles et les sessions supprimées.

## Modifications de l'historique

Réaffectation et suppression sont limitées aux sessions **locales terminées**, avec confirmation dans la fenêtre de détail. Les véhicules proposés pour la réaffectation sont ceux actuellement configurés ; les anciens véhicules restent disponibles pour filtrer leur historique. Ces actions ne changent ni la configuration de la borne, ni l'API Peugeot, ni une donnée externe.

La suppression masque définitivement la ligne et conserve une tombe technique pour empêcher qu'un checkpoint ou relevé tardif ne la recrée. Les réglages et compteurs de pilotage ne sont pas effacés. Sauvegarder le volume `/data` avant toute mise à jour reste la procédure normale de l'application.

## API

Toutes les routes requièrent la session connectée habituelle et les mutations héritent de la protection d'origine du serveur :

- `GET /api/v1/charging-sessions` : page, totaux, histogramme, répartitions, comparaison solaire mensuelle/annuelle et options.
- `GET /api/v1/charging-sessions/{id}` : détail.
- `PATCH /api/v1/charging-sessions/{id}` : `{vehicle_id, confirm:true}`.
- `DELETE /api/v1/charging-sessions/{id}` : `{confirm:true}`.
- `GET /api/v1/charging-sessions/export?format=csv|xlsx` : tous les résultats correspondant aux mêmes filtres.

Paramètres communs : `period=month|year|total`, `year`, `month`, `vehicle_id`, `device_id`, `group=solar|charger|vehicle`, `sort=date|charger|vehicle|energy|duration|solar|cost`, `direction=asc|desc`, `page`, `page_size` (1–100), `include_empty`. Les résultats de page sont bornés ; les statistiques portent sur toute la sélection. Les requêtes d'écran obsolètes sont annulées ; l'actualisation automatique est espacée de 30 secondes et suspendue quand l'onglet n'est pas visible.
