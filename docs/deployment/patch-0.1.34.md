# Mise à jour 0.1.34 — Jours rouges EDF Tempo et Manuel à durée

## Jours rouges Tempo

Nouveau champ facultatif dans Réglages → Intégrations → Home Assistant : **« Couleur Tempo du jour »**. Il attend l'entité de la couleur du jour, par exemple `sensor.rte_tempo_couleur_actuelle` de l'intégration RTE Tempo (valeurs « Bleu », « Blanc », « Rouge »). Champ vide : rien ne change par rapport à la 0.1.33.

Quand la couleur du jour est « Rouge » et que l'heure est hors des plages d'heures creuses de Planning (6 h → 22 h chez la plupart des abonnés) :

- **aucun usage du réseau en automatique** : ni programme voiture, ni heures creuses du ballon, ni courant de secours, ni appoint toléré pendant un nuage ;
- **le surplus solaire reste utilisé** : délai d'arrêt et temps minimal de fonctionnement sont ignorés, SEM réduit ou coupe dès que le compteur montre un import ;
- **à 6 h, tout Manuel en cours est coupé** (voiture et ballon). L'appareil repasse en automatique ; l'historique note « Fin du mode manuel : Heures pleines rouges » et le journal « Heures pleines rouges : fin du mode Manuel, retour en automatique » ;
- **le Manuel reste possible**. Dans SEM, une fenêtre « Jour rouge Tempo » demande confirmation pour Manuel, « Charger maintenant » et « Chauffer maintenant ». Un Manuel confirmé est noté « Confirmé : jour rouge, heures pleines ». Un Manuel demandé depuis Home Assistant est accepté et noté comme tel dans le journal.

Les cartes indiquent « Jour rouge, heures pleines : solaire seul ». L'en-tête affiche la couleur du jour et, pendant la période, « Heures pleines rouges : pas de réseau en automatique ».

**Couleur illisible** (HA hors ligne, capteur indisponible) : SEM garde la dernière couleur lue jusqu'au prochain passage à 6 h, puis fonctionne sans restriction et affiche « Couleur Tempo inconnue ». Pendant les 2 minutes qui suivent 6 h, une valeur pas encore mise à jour par le capteur est ignorée : le capteur RTE change de couleur une vingtaine de secondes après 6 h.

Sans aucune plage d'heures creuses dans Planning, toute la journée rouge compte comme heures pleines.

Le chauffage de la maison n'est pas concerné : il reste géré par Home Assistant.

## Manuel de la voiture à durée choisie

À côté du bouton Manuel de la voiture, une liste **« Durée » de 1 h à 12 h** (4 h par défaut ; la dernière durée choisie est retenue sur l'appareil). À la fin de la durée, la charge s'arrête et la voiture repasse en automatique, même si elle était en Pause avant. Le débranchement termine toujours le Manuel plus tôt. La carte affiche « Manuel jusqu'à HH:MM ». Changer la durée pendant un Manuel le relance avec la nouvelle durée.

« Charger maintenant » utilise la même durée. Le Manuel demandé depuis Home Assistant dure 4 h.

Une voiture déjà en Manuel au moment de la mise à jour reçoit une fin à « mise à jour + 12 h ».

API : `POST /api/v1/devices/{id}/manual` accepte `duration_minutes`. Pour une voiture, la valeur doit être un nombre entier d'heures de 60 à 720 ; sinon la réponse est **409** « Durée de 1 h à 12 h ». Pour le ballon, de 1 à 720 minutes (30 par défaut).

## Home Assistant (MQTT)

- Sur l'appareil « SEM – Installation », quand le champ Tempo est rempli : **« Couleur Tempo »** (Bleu, Blanc, Rouge) et **« Restriction Tempo active »**.
- La version de SEM s'affiche désormais sur chaque appareil SEM dans Home Assistant (« Version du micrologiciel »).

## Portainer

**Sauvegarder le volume /data avant la mise à jour.** Dès que la 0.1.34 enregistre les réglages, ils contiennent le champ `tempo_entity` de la section Home Assistant, que la 0.1.33 refuse. Un retour en arrière se fait donc avec la sauvegarde, pas avec le volume mis à jour.

Ensuite, utiliser SEM_VERSION=0.1.34 ou ghcr.io/macorou/solar-energy-manager:0.1.34. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite ne change pas.

Après le démarrage, renseigner « Couleur Tempo du jour » dans Réglages → Intégrations → Home Assistant.

**Retour en arrière :** restaurer la sauvegarde faite avant la 0.1.34. Supprimer aussi à la main, dans Home Assistant, les entités « Couleur Tempo » et « Restriction Tempo active » restées en place.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
