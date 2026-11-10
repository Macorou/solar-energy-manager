# Mise à jour 0.1.37 — Reprise de charge ignorée par la borne

## Problème

Après une pause de la voiture, la Wallbox peut accepter l'ordre de reprise (« Accepted ») sans l'appliquer : elle reste en pause (SuspendedEVSE) et ne propose aucun courant à la voiture. SEM attendait alors 5 minutes, passait en « Vérification requise », remettait 0 A et renvoyait le même ordre. Le 10 novembre, la charge a ainsi mis 10 minutes à reprendre : la borne a ignoré deux ordres identiques et appliqué le troisième en une seconde.

La borne ignore aussi parfois un arrêt à 0 A. SEM gérait déjà ce cas : au bout de 60 secondes, il ferme la session (RemoteStop).

## Changement

SEM traite maintenant une reprise ignorée de la même façon :

- si, 60 secondes après l'ordre de reprise, la borne est toujours en pause sans que la voiture consomme, SEM renvoie l'ordre ;
- si la borne l'ignore encore, SEM ferme la session en pause, attend sa fermeture (8 secondes au plus), puis ouvre une nouvelle session (RemoteStart). C'est la même méthode que pour le démarrage de chaque soir ;
- si la session ne se ferme pas, SEM ne démarre rien et affiche « Reprise ignorée : session en pause non fermée », puis passe en vérification comme pour toute commande sans réponse ;
- le délai de 60 secondes repart de zéro après une nouvelle pause, ou dès que la borne applique l'ordre.

L'énergie, le coût et la batterie estimée de la séance continuent sur la nouvelle session, comme lorsque SEM ferme une session dont l'arrêt a été ignoré.

Une pause demandée depuis l'application Wallbox pendant que SEM veut charger est désormais levée par une nouvelle session au bout d'environ une minute. Avant, SEM réessayait indéfiniment sans effet.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.37 ou ghcr.io/macorou/solar-energy-manager:0.1.37. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.36 démarre avec le même volume, sans restauration.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Le diagnostic s'appuie uniquement sur la lecture des journaux de SEM et de l'historique Home Assistant. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec la vraie borne n'est pas encore vérifié.
