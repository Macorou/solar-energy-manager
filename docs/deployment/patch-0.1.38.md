# Mise à jour 0.1.38 — Confirmation rapide des ordres du ballon

## Problème

SEM confirmait chaque arrêt et chaque chauffe du ballon par une lecture du cloud Ariston. Avec une interrogation toutes les 5 minutes, le ballon restait jusqu'à 5 minutes « En attente de confirmation ». Pendant ce temps, SEM retenait aussi les autres appareils par prudence.

Le 10 novembre au soir :
- l'arrêt demandé à 23:12:04 n'a été confirmé qu'à 23:16:59, alors que la mesure de puissance du ballon était à 0 W dès 23:12:36. La voiture n'a pas chargé pendant ces 5 minutes ;
- la chauffe relancée à 23:17:01 n'a été confirmée qu'à 23:22:04, alors que le ballon consommait déjà.

## Changement

La mesure de puissance du ballon dans Home Assistant confirme maintenant l'ordre dès qu'elle montre son effet :

- **arrêt** : le ballon chauffait au moment de l'ordre et sa mesure tombe à 0 W ensuite ;
- **chauffe** : le ballon ne chauffait pas au moment de l'ordre et se met à consommer ensuite, avec la bonne consigne.

La mesure doit être postérieure à l'ordre, et le ballon connecté et sans défaut. Dans tous les autres cas, la lecture du cloud Ariston reste nécessaire, comme avant : mesure déjà à 0 W avant l'ordre (le thermostat peut l'expliquer), ballon déjà en chauffe, consigne différente, mesure trop ancienne.

**Garde-fou :** un arrêt confirmé par la mesure peut coïncider avec l'arrêt du thermostat, le ballon restant allumé. S'il se remet à consommer, SEM renvoie l'ordre d'arrêt et l'inscrit dans son journal (`heater_redrawn_after_stop`).

Le réglage d'interrogation du cloud Ariston ne change pas : il sert encore dans les cas que la mesure ne permet pas de trancher.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.38 ou ghcr.io/macorou/solar-energy-manager:0.1.38. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.37 démarre avec le même volume, sans restauration. Une commande en cours garde la confirmation par le cloud Ariston.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Le diagnostic s'appuie uniquement sur la lecture des journaux de SEM et de l'historique Home Assistant. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec le vrai ballon n'est pas encore vérifié.
