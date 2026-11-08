# Mise à jour 0.1.36 — Prix mélangé pour la voiture et les sessions, licence MIT

## Prix de la voiture dans Home Assistant

« Prix de l'énergie de la voiture » publie maintenant toujours le mélange réseau et solaire de toute l'installation, le même que « Prix de l'énergie du site », que la voiture charge ou non.

Jusqu'ici, à l'arrêt, ce prix valait le tarif plein dès 1 W importé et 0 € dès 1 W exporté. La courbe sautait donc sans arrêt quand la maison passait de l'import à l'export. En charge, l'import était compté d'abord sur la voiture.

La courbe suit désormais la consommation de la maison, sans saut brutal pour quelques watts. Le prix du ballon garde sa règle actuelle.

## Sessions de charge

Le coût et la part solaire des sessions utilisent le même mélange : chaque kWh est compté avec la part réseau de toute l'installation à cet instant. Le prix publié et le coût affiché dans SEM racontent ainsi la même chose.

Les sessions terminées gardent leurs valeurs enregistrées. Une session en cours au moment de la mise à jour passe au nouveau calcul pour les kWh suivants.

Si la mesure du réseau ou de la production manque, le prix passe en « indisponible » et la session est marquée incomplète pour cette période.

## Prix du site

Le prix du site ne passe plus en « indisponible » quand l'export mesuré dépasse la production, ce qui arrivait quelques secondes les jours de nuages, les deux capteurs n'étant pas lus au même instant. Rien n'étant importé, SEM compte le prix solaire.

## Licence

Le code de SEM est désormais sous licence MIT. Le texte est dans `LICENSE` et copié dans l'image, dans `/opt/sem/licenses/`. Le code repris d'EVCC reste soumis à sa propre licence MIT.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.36 ou ghcr.io/macorou/solar-energy-manager:0.1.36. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.35 démarre avec le même volume, sans restauration. Les kWh déjà comptés restent comptés avec le prix mélangé.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
