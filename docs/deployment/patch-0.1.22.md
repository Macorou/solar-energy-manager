# Mise à jour 0.1.22 — Journaux de communication

Nouvel onglet **Journaux**, inspiré de la console EVCC : actualisation automatique avec pause/reprise, recherche, seuil de gravité FATAL/ERROR/WARN/INFO/DEBUG/TRACE, sélection de plusieurs zones et téléchargement TXT filtré. Console colorée adaptée aux thèmes sombre/clair et aux petits écrans. Les six entrées de navigation sont regroupées sur deux rangées sur téléphone.

Les diagnostics couvrent OCPP, Home Assistant, Peugeot, Ariston, le moteur, les événements et les requêtes en erreur. Les échanges OCPP sont résumés par action et mesures autorisées ; les délais portent le nom de l’appel. Aucun corps d’authentification ni trame brute n’est enregistré. Les données sensibles sont masquées avant la persistance.

Les journaux sont conservés dans le volume existant, jusqu’à sept jours et 10 000 lignes. La migration SQLite 3 ajoute uniquement leur table et son index. Les sessions de charge, la configuration et les accès restent conservés. Les anciennes sorties Docker ne sont pas importées rétroactivement.

## Portainer

1. Conserver le volume `/data` existant et sa clé de chiffrement ; sauvegarder le volume avant la mise à jour comme habituellement.
2. Définir `SEM_VERSION=0.1.22` ou l’image `ghcr.io/macorou/solar-energy-manager:0.1.22`.
3. Mettre à jour la Stack en téléchargeant l’image, avec les ports et volumes actuels.
4. Ouvrir **Journaux**. DEBUG affiche les communications courantes ; TRACE ajoute les mesures et résumés périodiques. ERROR filtre les erreurs et FATAL.

## Vérification

Les tests couvrent l’authentification, le masquage avant stockage/export, la conservation après réouverture/sauvegarde, la rétention, les filtres, les curseurs, la navigation dans de longues archives, les réponses réseau retardées, la pause et les délais OCPP. Les essais navigateur incluent Chromium et WebKit iPhone, largeurs 320/375/390/430 px et bureau, clair et sombre. Le test d’image CI vérifie également les journaux après redémarrage du conteneur.

Aucun appareil réel n’est commandé par les tests. Le moteur et les commandes restent ceux de la version précédente ; seuls leurs diagnostics sont ajoutés.

Voir [le fonctionnement des journaux](../features/journaux.md).
