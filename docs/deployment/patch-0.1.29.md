# Mise à jour 0.1.29 — Carte MQTT sur une installation existante

## Correction

Avec la 0.1.28, ouvrir Réglages → Intégrations → Services locaux → MQTT affichait une page vide sur une installation déjà en service. Les réglages enregistrés avant la 0.1.28 n'ont pas de section MQTT, et le serveur les renvoyait tels quels : le formulaire plantait sur cette section absente.

Le serveur complète désormais les réglages lus avec les valeurs par défaut des sections récentes. Pour MQTT, ce sont : sujet `sem`, préfixe de découverte `homeassistant`, et les autres champs vides. Un document qui ne pourrait pas être validé est renvoyé tel quel, comme avant.

Rien ne change pour les installations dont les réglages ont déjà été enregistrés en 0.1.28.

## Portainer

Sauvegarder le volume /data, puis utiliser SEM_VERSION=0.1.29 ou ghcr.io/macorou/solar-energy-manager:0.1.29. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3.

Un retour en arrière n'est possible :
- vers la 0.1.28 : avec le même volume ;
- vers la 0.1.27 ou une version antérieure : seulement avec la sauvegarde faite avant la 0.1.28, voir [patch-0.1.28.md](patch-0.1.28.md).

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage et des transports de test ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
