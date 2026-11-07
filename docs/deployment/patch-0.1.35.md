# Mise à jour 0.1.35 — Durée du Manuel du ballon

## Changement

La carte du ballon a maintenant, comme la voiture, une liste **« Durée »** à côté du bouton Manuel : 30 min, 1 h, 1 h 30, 2 h, 3 h ou 4 h. Elle démarre sur 30 min, la durée fixe des versions précédentes, et retient le dernier choix sur l'appareil.

- « Chauffer maintenant » utilise la même durée.
- Changer la durée pendant un Manuel le relance avec la nouvelle durée ; la carte affiche « Manuel jusqu'à HH:MM ».
- À la fin de la durée, le ballon revient au mode qu'il avait avant le Manuel.
- Pendant les heures pleines d'un jour rouge Tempo, la fenêtre de confirmation du ballon parle de « cette chauffe ».

Côté serveur, rien ne change : SEM acceptait déjà une durée de 1 à 720 minutes pour le ballon.

## Affichage

Sur ordinateur, la liste reste à côté de Manuel quand la carte a la place, sinon elle passe sur sa propre ligne sous les modes, comme pour la voiture. Sur téléphone, elle a sa propre ligne en 16 px pour éviter le zoom de Safari.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.35 ou ghcr.io/macorou/solar-energy-manager:0.1.35. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.34 démarre avec le même volume, sans restauration. Un Manuel du ballon en cours se termine à l'heure prévue.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
