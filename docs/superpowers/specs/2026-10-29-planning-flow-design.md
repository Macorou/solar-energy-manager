# Planning et flux graphiques

Interface validée dans la simulation `solar-planning-flow-preview.html`. Intégrer dans le frontend existant, avec les réglages en cartes déjà réalisés, puis pousser les deux changements sur la branche GitHub actuelle.

- Une seule barre : gris pour l’import réseau, vert pour le solaire consommé localement, jaune pour l’export. Le solaire exporté n’est pas compté une deuxième fois dans le vert.
- Sources au-dessus, usages en dessous. Icônes seules sur les repères. Les largeurs des usages correspondent à la consommation totale de chaque appareil, indépendamment de sa source. Les puissances restent dans la barre et la légende. Mesures manquantes ou incohérentes explicitement signalées.
- Remplacer les quatre tuiles et les phases de la vue d’ensemble par cette barre. Conserver les cartes illustrées de commande, bilan de recharge et raccourci planning.
- Planning en cartes voiture / ballon, objectifs, jours, horaires réseau et HC, autorisation solaire, priorités déplaçables avec alternative clavier, tableau des six réglages nuages par appareil. Conserver plusieurs véhicules/programmes et jours HC. Enregistrer via les API existantes sans armer implicitement.
- Navigation à quatre entrées : Vue d’ensemble, Planning, Historique, Réglages. Déplacer test de connexion, activation avec les trois attestations, désactivation et suppression dans la configuration des cartes Réglages.
- Respecter les paramètres existants, secrets et protections serveur. Aucun changement du moteur, aucune commande sur l’installation réelle pour les essais. Adaptation desktop/mobile et thèmes sombre/clair.

Approche retenue : réutiliser les contrats API et cartes existantes, nouveaux composants locaux pour la barre et les éditeurs du planning. La simulation est une référence visuelle, pas une source de valeurs fixes de production.
