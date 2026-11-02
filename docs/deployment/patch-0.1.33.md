# Mise à jour 0.1.33 — État de l'envoi vers Home Assistant

## Changement

Sur la vue d'ensemble, la carte Home Assistant annonçait encore une remontée vers Home Assistant « prévue ensuite », alors que la publication MQTT existe depuis la 0.1.28. Elle affiche désormais l'état réel de l'envoi, relu toutes les 10 secondes :

- **Connecté** : « Envoi vers Home Assistant par MQTT · dernier envoi HH:MM » ;
- **Désactivé** (sujet MQTT vide ou carte non configurée) : « Envoi vers Home Assistant désactivé (MQTT). » ;
- **Courtier injoignable** : « Envoi MQTT hors connexion : courtier injoignable. » ;
- **État illisible** : « État de l'envoi MQTT indisponible. »

Le badge de la carte passe au vert, « Accès enregistré », quand l'accès Home Assistant est configuré. Avant, il restait gris.

Le README du dépôt a aussi été réécrit : fonctions actuelles, matériel pris en charge, installation, mise à jour, et captures neuves sur données fictives.

## Portainer

Utiliser SEM_VERSION=0.1.33 ou ghcr.io/macorou/solar-energy-manager:0.1.33. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.32 démarre avec le même volume, sans restauration.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
