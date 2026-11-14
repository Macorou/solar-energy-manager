# Mise à jour 0.1.42 — Priorité du ballon sur la voiture

## Problème

Le 14 novembre au matin, le ballon (priorité 1) n'a jamais démarré alors que la voiture (priorité 2) chargeait au soleil :

1. Vers 9 h 55, le surplus n'était que de 1,6 à 2 kW. Le ballon chauffe à pleine puissance (environ 2,7 kW) ou pas du tout : il ne pouvait pas démarrer. La voiture, qui démarre dès 1,4 kW (6 A), a commencé à charger à 10 h 00. C'est normal : ce surplus ne servait à personne d'autre.
2. À 10 h 19, le surplus est monté à environ 4,9 kW. Le ballon a commencé son attente de surplus stable de 5 minutes, mais la voiture a augmenté sa charge à 4,4 kW une minute plus tard. Le ballon est revenu à « Surplus insuffisant » et y est resté toute la matinée.

SEM retirait du surplus tout ce que la voiture consommait déjà avant de servir le ballon. La priorité ne s'appliquait donc qu'au surplus restant, jamais à la puissance que la voiture pouvait rendre.

## Changement

- Pour un ballon, le surplus disponible compte aussi ce qu'une voiture de priorité plus basse, qui charge au soleil, peut rendre en descendant à son minimum (6 A).
- Quand le ballon démarre, la voiture est réduite dans la même décision à ce qu'il reste.
- Pendant les 5 minutes d'attente du ballon, la voiture ne démarre pas et n'augmente pas sur le surplus qu'il attend. Elle peut toujours utiliser ce qui dépasse.
- Ne rendent rien :
  - une voiture qui charge sur le réseau (mode manuel, heures creuses, créneau réseau d'un programme) ;
  - une borne dont la limite n'est pas appliquée ;
  - une voiture de priorité égale ou supérieure à celle du ballon.
- Un ballon qui ne peut pas démarrer laisse toujours le surplus à la voiture, comme avant.

Si le soleil baisse pendant que les deux fonctionnent, c'est la voiture qui se met en pause la première, après sa temporisation habituelle.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.42 ou ghcr.io/macorou/solar-energy-manager:0.1.42. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.41 démarre avec le même volume, sans restauration.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Le diagnostic s'appuie uniquement sur la lecture de l'historique Home Assistant. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec la vraie borne et le vrai ballon n'est pas encore vérifié.
