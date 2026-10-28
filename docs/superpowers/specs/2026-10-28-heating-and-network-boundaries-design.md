# Chauffe réseau/solaire et fin des créneaux — conception 0.1.7

Périmètre approuvé dans la conversation le 28 octobre (« Ok tu peux patch »).

## Objectif et contraintes

Regrouper la confirmation fiable des lectures HA asynchrones, deux consignes par
ballon et un arrêt explicite à la fin du créneau réseau des deux appareils.
Application indépendante FastAPI/React, Docker Linux amd64 et image GHCR privée.
Préserver les données, secrets, armement, priorités, limites et illustrations.
Aucun déploiement Portainer ou ordre matériel par l'assistant. Ne pas fusionner
la branche de développement dans main.

## Choix retenus

Une extension du moteur existant garde budgets et temporisations dans une même
décision. Une automatisation HA parallèle créerait deux contrôleurs ; un simple
champ d'interface laisserait objectif, commande et confirmation contradictoires.
Augmenter arbitrairement le seuil de deux secondes n'est pas retenu : utiliser les
vérifications actuelles des lectures HA en conservant une preuve d'effet physique.

## Confirmation

Confirmer un départ exige toujours une puissance réellement mesurée après
l'envoi, dans les limites de confirmation, ainsi qu'un état natif compatible.
Appairer réseau et appareil par leurs dates de vérification (ou dates de mesure
pour les sources sans vérification), réseau vérifié après l'appareil à deux
secondes au plus. Des dates fournisseur espacées de 11 secondes sont acceptables
si les deux valeurs sont relues dans le même état HA valide. Une ancienne valeur
simplement relue ne prouve pas l'effet d'un nouveau départ. Préserver tous les
contrôles d'arrêt natif, de valeurs invalides, d'horloges futures et de réservations.
Une commande de consigne seule peut être confirmée par une relecture native
postérieure montrant cette consigne, appareil allumé et puissance actuelle valide,
sans exiger une nouvelle augmentation de puissance.
Différencier attente de confirmation et incohérence électrique dans le motif.

## Deux consignes

Conserver `target` comme consigne réseau ; ajouter `solar_target`, nullable,
héritant de `target` sur les configurations existantes. Aucun relèvement implicite
de température lors de la mise à jour. L'utilisateur peut choisir 55/70 °C.
Contrôler les deux consignes selon les limites natives avant activation et au
moment des commandes. Ne pas affirmer que 70 °C est accepté par tout Ariston.

En automatique, sélectionner la consigne solaire lorsque le budget alloué au
ballon couvre sa puissance après priorités et marge. Pendant les HC aussi, un
surplus stable peut chauffer vers la consigne solaire. Utiliser les délais de
stabilisation et de perte de surplus existants. Hors créneau réseau, la chauffe
reste conditionnée au solaire ; en manuel, utiliser la consigne réseau.
Une perte durable du surplus revient à la consigne réseau si autorisée, sinon
suspend. Si l'eau est déjà au-dessus de la consigne réseau, ne pas continuer
sur le réseau vers la consigne solaire. Recalculer l'objectif atteint selon la
consigne sélectionnée, y compris au-dessus de 55 °C.

Transmettre la consigne dans une intention de commande immuable. Un changement
de consigne en chauffe ne doit pas rejouer un démarrage ; respecter les 60 secondes
de temporisation native. Afficher objectif effectif et origine réseau/solaire.

## Fin d'autorisation réseau

En automatique, la transition autorisé→interdit impose une suspension explicite
au premier cycle qui constate la fin, même avec du solaire disponible. Ne pas
attendre `stop_delay_s` ou `min_run_s`. Ballon : fin des HC ; voiture : fin du
créneau réseau effectif de ses programmes indépendants. Une autorisation valide
qui chevauche la première évite une fausse fin de créneau.
Conserver cette information de transition au redémarrage. Confirmer l'arrêt avant
toute reprise solaire, puis respecter surplus stable et délais de redémarrage.
Ne pas commander les appareils désarmés. Un manuel explicite reste une
autorisation réseau temporaire distincte. Motif explicite de fin de créneau.
L'envoi rapide ne garantit pas une réaction instantanée du cloud ou de la borne.

## Validation

Tests unitaires et intégrés avec horloge simulée et fournisseurs simulés ; aucune
commande réelle. Couvrir les dates HA décalées, les sources sans checked_at,
la confirmation sans saut de watts, la persistance/reprise, les frontières HC et
planning, la priorité, les nuages, les limites natives, les configurations
existantes et le formulaire. CI : Python, UI, schéma, build, navigateur et Docker.
Publier une nouvelle version privée immuable avec guide Portainer après succès.
