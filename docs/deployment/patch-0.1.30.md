# Mise à jour 0.1.30 — Part solaire des sessions partiellement mesurées

## Changement

Avant cette version, la part solaire d'une session de charge disparaissait dès qu'une partie de son énergie n'avait pas d'origine connue :
- SEM redémarré ou mis à jour pendant la charge ;
- charge commencée avant que SEM ne la voie.

Elle restait alors indisponible jusqu'à la fin de la session, dans SEM comme dans Home Assistant.

La part solaire porte désormais sur l'énergie d'origine connue. Si une partie de l'énergie de la session n'a pas d'origine connue, la valeur est marquée comme partielle :
- **Carte de la voiture** : « Part solaire partielle » au lieu de « Part solaire estimée ».
- **Historique des sessions** : la mention « Partielle » sous la valeur. Le détail précise que la part porte sur l'énergie d'origine connue, et le total aussi.
- **Exports CSV et Excel** : nouvelle colonne « Part solaire partielle ».
- **Home Assistant** : l'entité « Part solaire de la session » reçoit l'attribut `partial`, comme l'énergie et le coût de la session.

La part ne reste indisponible que si aucune énergie de la session n'a d'origine connue.

## Historique existant

Au premier démarrage, les sessions déjà enregistrées sont reprises une seule fois :
- une session qui avait une part solaire la garde, non partielle ;
- une session sans part solaire en reçoit une, calculée sur ses kWh solaire et réseau enregistrés et marquée partielle.

## Portainer

Sauvegarder le volume /data, puis utiliser SEM_VERSION=0.1.30 ou ghcr.io/macorou/solar-energy-manager:0.1.30. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3.

Un retour en arrière n'est possible :
- vers la 0.1.28 ou la 0.1.29 : avec le même volume. Les parts solaires reprises s'y affichent sans la mention « partielle » ;
- vers la 0.1.27 ou une version antérieure : seulement avec la sauvegarde faite avant la 0.1.28, voir [patch-0.1.28.md](patch-0.1.28.md).

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage et des transports de test ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
