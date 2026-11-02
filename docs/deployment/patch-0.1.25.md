# Mise à jour 0.1.25 — Charge de nuit garantie et régulation plus stable

Cette version vise un objectif : une voiture en mode automatique ne doit pas cesser de charger sans raison pendant son créneau réseau. Elle rend aussi la régulation solaire plus calme et corrige plusieurs cas où une mesure ou une confirmation manquante arrêtait la charge.

## Régulation de la borne

- Le courant n’est modifié que si l’écart dépasse 0,5 A, et au plus une fois toutes les 15 secondes (les baisses de protection restent immédiates). En simulation, le nombre de commandes envoyées baisse d’environ moitié ; l’effet réel reste à observer.
- La raison « limite de phase » n’est affichée que lorsqu’elle réduit vraiment la puissance.
- Une seule réservation de puissance par borne : la commande suivante la remplace, et elle est libérée dès que la borne confirme. Un arrêt perdu ne bloque plus la charge suivante.
- Si la voiture refuse la puissance proposée (état SuspendedEV) pendant 2 minutes, le surplus est rendu au ballon et l’état de la borne est relu.

## Mesures en retard

- Une mesure en retard de moins de 60 secondes ne coupe plus la charge : la puissance actuelle est conservée tant que la phase garde de la marge, sinon la charge s’arrête par sécurité.
- Sans compteur réseau, une commande de puissance peut être confirmée par la borne elle-même (courant proposé, état ou puissance OCPP).
- Nouveau réglage dans Réglages → Installation : « Courant de secours sans mesure réseau (A, 0 = arrêt) ». Par défaut 0 : sans mesure réseau, la charge s’arrête comme avant. Avec 16, la charge réseau continue à 16 A pendant une coupure de Home Assistant ; la limite de phase n’est alors plus surveillée.

## Limite de recharge non appliquée

Quand la borne n’applique pas la limite demandée, la charge est coupée puis relancée automatiquement après 5 minutes, avec un délai qui double jusqu’à 30 minutes. L’historique est oublié après 2 heures sans incident ou au débranchement. L’événement « Limite de recharge non appliquée » apparaît dans l’historique.

## Batterie de la voiture pendant le créneau réseau

- Pendant un créneau réseau (programmé ou manuel), la charge continue même sans pourcentage de batterie utilisable : la voiture s’arrête alors d’elle-même une fois pleine (« Batterie inconnue : charge poursuivie jusqu’à l’arrêt par la voiture »).
- L’estimation de la session (dernier pourcentage Peugeot plus l’énergie chargée) continue pendant une panne de l’API Peugeot et arrête la charge à l’objectif, même si l’index d’énergie de la borne ne peut plus être vérifié (« Objectif atteint (dernière estimation) »).
- Un pourcentage Peugeot conservé pendant une erreur de l’API n’est plus utilisé : la voiture a pu rouler depuis. Une nouvelle session attend une réponse Peugeot avant d’estimer. Une donnée Peugeot ancienne mais renvoyée sans erreur reste utilisée.
- En mode solaire, l’absence de pourcentage arrête toujours la charge, comme avant.
- Un avertissement s’affiche sur la carte de la voiture lorsque le créneau programmé semble trop court pour atteindre l’objectif. Le programme n’est pas modifié.

## Portainer

Utiliser SEM_VERSION=0.1.25 ou ghcr.io/macorou/solar-energy-manager:0.1.25, télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3.

Sauvegarder le volume /data avant la mise à jour : dès que 0.1.25 enregistre les réglages, ils contiennent le nouveau courant de secours, que 0.1.24 refuse. Un retour à 0.1.24 se fait donc avec la sauvegarde, pas avec le volume mis à jour.

Après la mise à jour, régler si souhaité le courant de secours (par exemple 16 A) dans Réglages → Installation.

Aucune commande matérielle n’a été envoyée pendant le développement. Les essais utilisent un stockage et des transports de test ; aucun historique, accès ni réglage de l’installation réelle n’a été modifié par ces tests.
