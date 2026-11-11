# Mise à jour 0.1.40 — Mesures décalées, coupures brèves et horloges

## Problème

Un audit du pilotage a relevé quatre défauts :

1. **Double comptage après un changement de puissance.** Quand la borne annonce une pause, sa puissance passe à 0 W tout de suite. Les compteurs réseau et de phase Home Assistant gardent leur dernière lecture, qui contient encore la voiture, jusqu'à leur prochaine mise à jour. La voiture était alors comptée deux fois : le ballon en marche pouvait être coupé faute de place, et avec la limite par phase, une pause de la borne pouvait faire envoyer un vrai arrêt à la voiture. Le même décalage existait quand le thermostat du ballon s'arrêtait.
2. **Mesure manquante.** Une seule lecture réseau, de phase ou d'appareil indisponible (capteur un instant « indisponible », reconnexion à Home Assistant) arrêtait aussitôt les appareils en marche.
3. **Statut de fin de session rejeté.** La fin de session était datée à l'heure de SEM. Le statut « Available » envoyé juste après le débranchement, daté par l'horloge de la borne, pouvait être rejeté comme plus ancien.
4. **Horloges en avance.** Une mesure ou un statut daté de quelques secondes dans le futur était refusé, sans trace dans le journal.

## Changement

- Après un saut de puissance d'au moins 300 W sur un appareil, SEM attend que les compteurs réseau et de phase soient relus avant de recalculer la place disponible, pendant 30 s au plus. Pendant ce temps, il maintient ce qui tourne, n'augmente rien et ne démarre rien. Une vraie surcharge réduit toujours la charge immédiatement.
- Une mesure réseau, de phase ou d'appareil absente pendant 20 s au plus maintient la puissance des appareils en marche, sans rien augmenter ni démarrer. Au-delà, les appareils s'arrêtent comme avant. Pendant ces 20 s, le disjoncteur n'est pas surveillé ; un courant de secours réglé s'applique toujours immédiatement.
- Les statuts de la borne sont classés avec la seule horloge de la borne, puis datés à leur réception. La fin de session suit la même règle que l'ouverture depuis la 0.1.39 : le « Available » après débranchement est conservé.
- Une tolérance de 5 s s'applique aux mesures datées dans le futur. Un statut ou une mesure de la borne en avance est accepté et daté à sa réception. Une avance de plus de 5 s de la borne ou de Home Assistant est signalée une fois dans le journal, et chaque statut ignoré y laisse une ligne.

Nouveaux motifs visibles : « Mesure réseau momentanément indisponible : puissance maintenue », « Courant réseau momentanément indisponible : puissance maintenue », « Mesures en cours de mise à jour : démarrage différé ».

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.40 ou ghcr.io/macorou/solar-energy-manager:0.1.40. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.39 démarre avec le même volume, sans restauration.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec la vraie borne et le vrai ballon n'est pas encore vérifié.
