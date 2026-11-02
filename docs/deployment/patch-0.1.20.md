# Mise à jour 0.1.20 — Sessions de charge

La nouvelle rubrique **Sessions de charge** utilise les compteurs existants de Solar Energy Manager : périodes Mois/Année/Total, énergie solaire/réseau, coûts et prix moyen pondéré, regroupements par véhicule/borne, filtres, tri, pagination, détail et exports CSV/Excel. Les données incomplètes restent signalées. Le CO₂ est masqué faute de données fiables.

Le journal **Historique**, le pilotage, les réglages et les accès chiffrés sont conservés. Les illustrations transparentes et les corrections mobiles de 0.1.19 restent incluses.

## Portainer

1. Sauvegarder le volume persistant `/data`, avec sa base et sa clé de chiffrement.
2. Dans la Stack, définir `SEM_VERSION=0.1.20`, ou utiliser explicitement `ghcr.io/macorou/solar-energy-manager:0.1.20`.
3. Mettre à jour la Stack avec téléchargement de la nouvelle image. Conserver le volume existant et les ports de l'installation.
4. Vérifier la version 0.1.20 dans l'application puis ouvrir **Sessions de charge**. Aucun nouvel identifiant OCPP, Peugeot ou Home Assistant n'est nécessaire.

La migration SQLite est automatique et additive dans `/data/app.db`. Elle récupère la dernière session encore présente pour chaque borne. Les sessions écrasées par le stockage des versions précédentes ne peuvent pas être reconstituées. À partir de cette version, les sessions sont conservées indépendamment des suivantes ; pauses, reprises et redémarrages ne créent pas de doublons.

Les sessions complètement mesurées à zéro sont masquées par défaut, avec une option pour les inclure. Une absence de compteur ou d'index terminal confirmé reste visible comme mesure partielle. Les suppressions et réaffectations concernent uniquement l'historique local terminé, avec confirmation.

Voir [les conventions de calcul et les limites de récupération](../features/charging-sessions.md) et [l'étude des sources/licences EVCC](../research/2026-10-30-evcc-sessions.md).

## Validation avant publication

- Backend : 366 tests réussis ; un test Docker ignoré localement, exécuté par la CI avec l'image construite.
- Frontend : 82 tests réussis, compilation TypeScript/Vite réussie.
- Navigateurs : 16 parcours réussis, dont Chromium et WebKit iPhone, largeurs 320 à 1440 px, thèmes clair et sombre.
- Relecture indépendante : aucun problème critique ou important restant après corrections.
- Aucun appareil réel commandé pendant les tests. La publication GitHub déclenche les vérifications complètes puis la construction et le contrôle de l'image GHCR privée.
