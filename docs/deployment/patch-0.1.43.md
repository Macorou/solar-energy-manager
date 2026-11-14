# Mise à jour 0.1.43 — Activer les programmes de charge depuis Home Assistant

## Problème

Depuis Home Assistant, on pouvait changer l'objectif de chaque programme de charge, mais pas activer ou désactiver un programme. Avec plusieurs programmes pour la voiture, il fallait passer par la page Planning de SEM pour choisir lesquels s'appliquent.

## Changement

Quand les commandes Home Assistant sont activées (Réglages › MQTT), SEM publie pour chaque programme de charge de la voiture :

- **Programme – <nom>** : un interrupteur (`switch`), allumé quand le programme est actif. L'éteindre fait comme décocher « Programme actif » dans Planning ; le programme reste enregistré avec ses réglages.
- **Objectif – <nom>** : le réglage d'objectif existant, inchangé.

Les programmes actifs s'appliquent toujours tous ensemble, chacun sur ses jours. Si l'activation d'un programme crée un conflit avec un autre programme actif (même voiture, même échéance, un jour en commun et un début réseau différent), SEM la refuse, l'interrupteur se remet sur arrêt et le journal l'indique.

Exemple d'identifiants dans Home Assistant, pour la borne « Wallbox Pulsar Plus » et un programme « Cette nuit » : `switch.sem_wallbox_pulsar_plus_programme_cette_nuit` et `number.sem_wallbox_pulsar_plus_objectif_cette_nuit`.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.43 ou ghcr.io/macorou/solar-energy-manager:0.1.43. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.42 démarre avec le même volume, sans restauration. Les interrupteurs « Programme – … » restent alors dans Home Assistant comme indisponibles : les supprimer à la main si besoin.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec le vrai Home Assistant n'est pas encore vérifié.
