# Mise à jour 0.1.27 — Surplus solaire sans batterie connue et messages d’attente corrigés

## Charge solaire sans pourcentage de batterie

Sans pourcentage utilisable (panne de l’API Peugeot, estimation pas encore disponible), le mode solaire refusait de charger la voiture (« Batterie indisponible »). Il charge désormais sur le surplus seul, jusqu’à ce que la voiture arrête elle-même la charge. Le réseau n’est jamais utilisé en dehors d’un créneau réseau. Une estimation de session, même invérifiable, arrête toujours la charge à l’objectif sur surplus (ou à l’objectif s’il n’y en a pas). La raison affichée est « Batterie inconnue : charge poursuivie jusqu’à l’arrêt par la voiture ».

## Message « aucune augmentation »

Pendant qu’une commande du ballon attend sa confirmation, SEM ne laisse démarrer ou augmenter aucun appareil. Ce message s’affichait sur tous les appareils, y compris un ballon déjà en chauffe à pleine puissance. Il n’apparaît plus que lorsqu’un changement est réellement retenu : « démarrage différé » pour le ballon ou une voiture à l’arrêt, « aucune augmentation » pour une voiture déjà en charge. Un appareil non concerné garde sa raison habituelle ; le badge « En attente de confirmation » reste affiché pour l’appareil dont la commande attend.

## Portainer

Sauvegarder le volume /data, puis utiliser SEM_VERSION=0.1.27 ou ghcr.io/macorou/solar-energy-manager:0.1.27, télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3 et aucun champ de réglage n’est ajouté : un retour à 0.1.26 reste possible avec le même volume.

Aucune commande matérielle n’a été envoyée pendant le développement. Les essais utilisent un stockage et des transports de test ; aucun historique, accès ni réglage de l’installation réelle n’a été modifié par ces tests.
