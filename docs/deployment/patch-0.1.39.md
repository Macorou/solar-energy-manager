# Mise à jour 0.1.39 — Charge préservée au redémarrage de SEM

## Problème

Lors de la mise à jour en 0.1.38 (11 novembre, 01:27), la voiture chargeait. Deux défauts ont coupé puis retardé la charge :

1. **Arrêt au redémarrage.** Pendant les quelques secondes où la Wallbox n'était pas encore reconnectée, SEM a tenté de l'arrêter parce qu'il la voyait indisponible. L'ordre ne pouvait pas partir ; il est devenu « Résultat de commande inconnu », et SEM a coupé la charge par sécurité dès la reconnexion.
2. **Statut masqué à l'ouverture d'une session.** Le secours de la 0.1.37 a bien ouvert une nouvelle session à 01:28:48. La borne s'est aussitôt remise en pause, mais SEM est resté sur « Preparing » : la réponse à StartTransaction fixait cet état à l'heure de SEM, et le statut suivant, daté un peu plus tôt par l'horloge de la borne, était rejeté comme plus ancien. Le secours ne pouvait donc pas se relancer. La charge n'a repris qu'à 01:31:29, sur un ajustement de courant.

## Changement

- SEM n'envoie plus d'ordre à une borne déconnectée. Elle garde sa dernière limite, et SEM reprend la décision dès qu'elle se reconnecte. Un redémarrage ou une mise à jour de SEM n'interrompt donc plus une charge. Un arrêt de fin d'heures creuses reste envoyé dès la reconnexion.
- L'ouverture d'une session ne remplace plus un statut envoyé par la borne après le début de cette session. L'état « Preparing » est daté avec l'heure de la borne, comme ses autres statuts.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.39 ou ghcr.io/macorou/solar-energy-manager:0.1.39. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.38 démarre avec le même volume, sans restauration.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Le diagnostic s'appuie uniquement sur la lecture des journaux de SEM et de l'historique Home Assistant. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec la vraie borne n'est pas encore vérifié.
