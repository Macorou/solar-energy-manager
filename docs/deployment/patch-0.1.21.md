# Mise à jour 0.1.21 — Corrections des sessions de charge

- **Aperçu sur téléphone** : deux colonnes configurables, chacune proposant Chargé, Coût, Part solaire et Durée. Les colonnes peuvent afficher l'énergie et le coût côte à côte ; leurs totaux et tris suivent les mesures choisies.
- **Vue €** : disponible dès qu'un montant est connu, même si la mesure de la session est partielle. Les montants partiels restent explicitement qualifiés. Les coûts absents ne deviennent pas zéro ; les coûts nuls ou négatifs sont conservés. Le prix moyen au kWh reste réservé aux mesures complètes.
- **Batterie au début/à la fin** : le départ est figé avant la charge et ne suit plus le dernier relevé Peugeot. Une transaction déjà commencée ne fournit pas artificiellement un départ. Les anciens départs ambigus de 0.1.20 sont réparés automatiquement si la référence initiale persistante le permet ; sinon le détail affiche Non enregistrée.

Le pilotage, les limites de charge, les accès OCPP/Peugeot/Home Assistant et le volume existant restent compatibles. La correction porte sur l'historique et sa présentation.

## Portainer

1. Sauvegarder le volume persistant `/data` avec la base et sa clé de chiffrement.
2. Définir `SEM_VERSION=0.1.21` dans la Stack, ou utiliser `ghcr.io/macorou/solar-energy-manager:0.1.21`.
3. Mettre à jour la Stack en téléchargeant la nouvelle image, avec le même volume et les mêmes ports.
4. Vérifier la version 0.1.21 et ouvrir Sessions de charge. Choisir Coût dans une colonne de l'Aperçu ; le mode € affiche également les montants partiels connus.

La réparation de provenance est automatique dans la base SQLite existante, sans nouveau volume ni identifiant. Les affectations et suppressions locales sont préservées. Une valeur de départ définitivement absente ne peut pas être retrouvée rétroactivement.

## Validation avant publication

- Backend : 375 tests réussis, un test d'image Docker ignoré localement et exécuté en CI.
- Frontend : 85 tests réussis ; compilation TypeScript/Vite réussie.
- Navigateurs : 18 parcours réussis, Chromium et WebKit iPhone, thèmes clair/sombre, largeurs mobiles de 320 à 430 px et vue ordinateur.
- Relecture indépendante : aucun point critique ou important restant après correction du cas de transaction déjà commencée.
- Aucun appareil réel commandé pendant les tests. La CI vérifie l'application et l'image Docker avant publication GHCR privée.

Voir [les conventions de mesure et de récupération](../features/charging-sessions.md).
