# Mise à jour 0.1.44 — Plus de blocage pour la nuit après un démarrage ignoré par la borne

## Problème

Dans la nuit du 14 au 15 novembre, la voiture a chargé de 22 h 00 à 23 h 53, puis plus du tout :

1. À 23 h 53, un pic de consommation sur L1 (25,9 A) a fait suspendre la charge, comme prévu.
2. De 23 h 53 à 0 h 26, la borne a refusé toutes les reprises à 9 A : elle acceptait la limite, puis restait en SuspendedEVSE. SEM a rouvert une session toutes les 2 minutes, 17 fois.
3. À 0 h 26, la borne a accepté une nouvelle demande de session (RemoteStartTransaction) sans jamais l'ouvrir : elle est restée en « Finishing ».
4. À 0 h 27, SEM a demandé l'arrêt. Il ne valide un arrêt que si aucun démarrage n'est en attente, or le démarrage de 0 h 26 est resté « en attente » pour toujours. L'arrêt n'a jamais été confirmé : SEM est resté en « Résultat de commande inconnu : vérification requise » et n'a plus rien commandé, même en mode Manuel, jusqu'à ce que la voiture soit débranchée.

## Changement

- Un démarrage accepté par la borne qui n'est suivi d'aucune ouverture de session dans la minute est abandonné. Le journal l'indique : « Démarrage accepté par la borne sans ouverture de session : abandonné ».
- L'arrêt suivant est alors confirmé normalement par l'état de la borne, et SEM reprend la main tout seul : il redemande une session à l'offre suivante au lieu de rester bloqué.
- Si la borne ignore encore la demande, SEM recommence au cycle suivant au lieu de se bloquer pour la nuit.

Ce correctif n'explique pas pourquoi la borne a refusé les reprises à 9 A entre 23 h 53 et 0 h 26 ; ce point reste à observer.

Au premier démarrage de la 0.1.44, le démarrage resté en attente depuis la nuit est abandonné et l'arrêt de 0 h 27 est confirmé : le blocage actuel se lève sans débrancher la voiture.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.44 ou ghcr.io/macorou/solar-energy-manager:0.1.44. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.43 démarre avec le même volume, sans restauration.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Le diagnostic s'appuie uniquement sur la lecture des journaux de SEM et de l'historique Home Assistant. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec la vraie borne n'est pas encore vérifié.
