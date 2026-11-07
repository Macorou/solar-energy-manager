# Jours rouges EDF Tempo et Manuel à durée — conception

## Intention

L'utilisateur est au tarif EDF Tempo. Les heures pleines des jours rouges (6 h → 22 h) coûtent plusieurs fois le prix normal. Jusqu'ici, une automatisation Home Assistant pilotait EVCC pour éviter de charger la voiture ces heures-là. EVCC n'est plus en service : aujourd'hui, rien n'empêche SEM d'acheter du réseau aux heures pleines rouges, par exemple via la tolérance anti-nuages ou un programme voiture.

Objectif : **SEM n'achète jamais de courant réseau en automatique pendant les heures pleines d'un jour rouge.** L'utilisateur garde la main en manuel pour les urgences, avec un avertissement clair.

Cette conception réalise l'« Extension Tempo » prévue au §19 de la conception initiale (`2026-10-26-solar-energy-manager-design.md`), dans une version volontairement simple : pas d'anticipation, pas de prévision.

## Règles décidées par l'utilisateur

### Jour rouge, heures pleines (6 h → 22 h)

- **Aucun usage réseau en automatique**, pour la voiture comme pour le ballon. À 6 h, tout ce que SEM alimente depuis le réseau en automatique s'arrête.
- **Le surplus solaire reste utilisable**, sans jamais prendre sur le réseau : pas de tolérance d'appoint, pas de délai anti-nuages qui laisserait tirer du réseau pendant un passage nuageux. Dès que le surplus ne couvre plus la puissance minimale de l'appareil, SEM réduit ou coupe immédiatement.
- **Le manuel reste possible** (« Charger maintenant », « Chauffer maintenant », bouton Manuel), car c'est une décision explicite. Dans l'interface de SEM, il demande une confirmation par une fenêtre : jour rouge, heures pleines, tarif le plus cher, continuer ?
- **Un Manuel déjà en cours à 6 h est coupé aussi** (voiture et ballon). L'appareil repasse en automatique, donc en solaire seul. Pour continuer sur le réseau, l'utilisateur relance un Manuel et confirme la fenêtre.
- **Manuel venant de Home Assistant** (commande MQTT de la 0.1.31) : accepté pendant les heures pleines rouges, car il vient de l'utilisateur, et écrit dans le journal comme tel. L'avertissement côté HA est fait dans le tableau de bord, et non dans SEM : le bouton Manuel de la vue « voiture » demande une confirmation quand `sensor.rte_tempo_couleur_actuelle` vaut « Rouge » et qu'on est en heures pleines. Cette modification de HA est faite après la publication, avec sauvegarde et accord de l'utilisateur. Elle ne fait pas partie du code de SEM.

### Couleur inconnue

Si la couleur ne peut pas être lue (HA hors ligne, capteur indisponible, valeur inattendue), SEM garde la dernière couleur lue tant qu'elle concerne le jour Tempo en cours, c'est-à-dire jusqu'au prochain passage à 6 h. Au-delà, il fait comme un jour normal (pas de restriction) et affiche un avertissement « Couleur Tempo inconnue » sur la vue d'ensemble. *Durée de validité : choix du concepteur.*

### Jour rouge, heures creuses (22 h → 6 h)

Fonctionnement normal : programmes voiture, heures creuses du ballon, surplus.

### Jours bleus et blancs

Aucun changement.

### Chauffage

Hors de SEM. Il reste géré par le Smart Heat Manager de Home Assistant, qui a déjà sa propre restriction Tempo. SEM n'y touche pas.

## Manuel de la voiture à durée choisie

Aujourd'hui (depuis 0.1.23), le mode Manuel de la voiture n'a pas de fin, sauf au débranchement (0.1.31). Il pourrait donc continuer de charger pendant les heures pleines d'un jour rouge sans nouvelle décision.

Décision de l'utilisateur :

- À côté du bouton Manuel de la voiture, une **liste déroulante de 1 h à 12 h**, par pas d'une heure.
- **À la fin de la durée, la charge s'arrête** et la voiture repasse en mode automatique, qui applique les règles du moment, y compris celles d'un jour rouge.
- L'option « jusqu'au débranchement » disparaît. Le débranchement continue de terminer le Manuel plus tôt (règle 0.1.31).
- « Charger maintenant » utilise la même durée que la liste.

Le ballon garde son fonctionnement : sa commande manuelle est déjà un cycle temporaire de 30 minutes.

## Source de la couleur

La couleur Tempo est lue dans Home Assistant, comme les autres mesures. L'utilisateur a l'intégration **RTE Tempo** : `sensor.rte_tempo_couleur_actuelle` (valeurs « Bleu », « Blanc », « Rouge ») et `sensor.rte_tempo_prochaine_couleur`. Dans Réglages → Intégrations → Home Assistant, un nouveau champ facultatif « Couleur Tempo du jour » accepte l'entité. Champ vide : fonction désactivée, comportement identique à la 0.1.33.

L'heure de bascule HP/HC est celle des **plages d'heures creuses déjà saisies dans Planning** (22 h → 6 h chez l'utilisateur), pas une heure figée dans le code.

**Règle exacte :** la restriction s'applique quand la couleur du jour vaut « Rouge » **et** que l'heure courante est hors des plages d'heures creuses globales de Planning. Le capteur RTE suit le jour Tempo (6 h → 6 h) : son prochain changement est annoncé à 6 h, heure de Paris. Entre 0 h et 6 h, il donne donc encore la couleur du jour commencé la veille à 6 h, et ces heures sont creuses. Les réglages d'heures creuses propres à un appareil ne changent pas cette règle. *Choix du concepteur :* sans aucune plage d'heures creuses saisie, toute la journée rouge compte comme heures pleines.

## Affichage

- Une pastille sur la vue d'ensemble : couleur du jour, et le rappel « Heures pleines rouges : pas de réseau en automatique » pendant la période concernée.
- Les cartes voiture et ballon donnent la raison quand un appareil est bloqué ou coupé par la règle, par exemple « Jour rouge, heures pleines : solaire seul ».
- Chaque blocage, coupure ou confirmation manuelle est écrit dans l'historique et dans les journaux.
- Publication MQTT : la couleur du jour et l'état « restriction Tempo active » sur l'appareil SEM – Installation.

## Non-objectifs

- Pas d'anticipation : SEM ne charge pas davantage la veille d'un jour rouge.
- Pas de prévision de couleur, pas de modèle de prix.
- Pas de pilotage du chauffage.
- Pas de règle particulière pour les jours blancs.

## Anti-objectifs

Ce serait un échec, même si le reste fonctionne :

- La moindre consommation réseau automatique en heures pleines rouges, y compris un appoint de quelques centaines de watts pendant un nuage.
- Un mode Manuel lancé un autre jour qui continue de charger en heures pleines rouges au-delà de la durée choisie.
- Une fenêtre de confirmation qui apparaît en dehors des heures pleines rouges, ou un Manuel bloqué quand l'utilisateur en a besoin.

## Précisions (choix du concepteur, modifiables)

- **« Pas de réseau » mesurable.** Pendant la restriction : tolérance d'appoint à 0 et délai d'arrêt à 0. Réduction ou coupure dès la première mesure du compteur réseau qui montre un import attribuable à l'appareil. Le retard propre aux mesures (quelques secondes) est accepté. SEM se fie au compteur réseau : la décharge d'une éventuelle batterie domestique n'est pas gérée (hors périmètre de la conception initiale).
- **Durée du Manuel.** Valeur par défaut 4 h. La dernière durée choisie est retenue pour chaque voiture.
- **Voitures déjà en Manuel au moment de la mise à jour.** Elles reçoivent une fin à « mise à jour + 12 h » : une charge en cours n'est pas coupée brutalement, mais elle est bornée.
- **Fenêtre de confirmation.** Elle s'affiche aussi pour « Chauffer maintenant », pour le Manuel du ballon et pour un changement de durée pendant un Manuel en cours, dès lors que l'on est en heures pleines rouges.
- **Historique.** Une entrée seulement aux changements d'état (début et fin de la restriction, appareil coupé, Manuel confirmé), jamais à chaque cycle.

## Ce qui reste au constructeur

- Le placement exact de la restriction dans le moteur. Repères existants : `DevicePolicy` (`import_tolerance_w`, `stop_delay_s`, `off_peak`, `manual_until`), la construction des politiques dans `runtime/coordinator.py`, l'éligibilité réseau dans `engine/engine.py`.
- La forme exacte de la pastille et de la fenêtre, dans le style existant (sombre et clair, téléphone, iPhone/Safari).
- La migration des voitures déjà en Manuel sans durée au moment de la mise à jour.
- Les textes exacts, en français.
