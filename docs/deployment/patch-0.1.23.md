# Mise à jour 0.1.23 — Mode manuel persistant de la voiture

Le bouton Manuel et Charger maintenant sélectionnent désormais un mode de recharge sans expiration pour la voiture. Les versions précédentes fixaient une durée de 30 minutes puis restauraient le mode automatique précédent. Le mode choisi est conservé après une nuit, un redémarrage et un débranchement ; seuls un changement explicite de mode (Automatique/Pause ou réglage utilisateur) le remplacent.

La limite de batterie, les limites électriques, les mesures nécessaires et les confirmations de commandes restent applicables. Atteindre l’objectif arrête la recharge sans faire quitter le mode Manuel. Le cycle manuel temporaire du ballon conserve son fonctionnement.

Les anciens appels envoyant duration_minutes=30 restent acceptés pour la voiture, avec until=null. Une ancienne échéance est effacée si la voiture est encore en manuel. Une voiture déjà revenue en automatique n’est pas forcée en manuel à la mise à jour : l’utilisateur doit le sélectionner à nouveau. Le retour Automatique retrouve la politique précédente, y compris après Manuel → Pause → Automatique.

Le patch supprime aussi la ligne technique Demande … W/kW des cartes du dashboard, conformément à la demande précédente. Le statut principal, la puissance et les journaux restent disponibles.

## Portainer

Utiliser SEM_VERSION=0.1.23 ou ghcr.io/macorou/solar-energy-manager:0.1.23, télécharger la nouvelle image et conserver le volume /data et les ports existants. Après la mise à jour, sélectionner Manuel une fois si la voiture est actuellement en automatique.

Aucune commande matérielle n’a été envoyée pendant le développement. Les essais utilisent un stockage et des transports de test ; aucun historique, accès ni réglage de l’installation réelle n’a été modifié par ces tests.
