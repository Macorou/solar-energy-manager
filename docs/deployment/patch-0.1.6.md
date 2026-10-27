# Patch 0.1.6 — faire aboutir la demande de chauffe

Un clic « Chauffer maintenant » pouvait être enregistré alors qu'un ancien
arrêt automatique restait en attente. L'utilisateur voyait « Arrêt demandé »
et une réservation de 2570 W. L'arrêt avait été généré par le contrôleur durant
la reconnexion ; il ne correspondait pas à la demande de chauffe de l'utilisateur.

## Corrections

- Pour un arrêt Ariston, une nouvelle lecture native après l'ordre doit indiquer
  connecté, sans défaut et off. Elle est croisée avec une puissance HA <=20 W
  vérifiée après l'ordre et une lecture réseau valide et cohérente. Cette
  combinaison peut confirmer l'arrêt même si la valeur 0 W n'a pas changé de date.
- Une ancienne valeur 0 W seule ne confirme rien. Les données indisponibles,
  trop anciennes, futures ou contradictoires ne libèrent pas la réservation.
- Une commande en cours d'envoi conserve sa réservation. Tout arrêt du ballon
  requiert un état natif off valide, même avec une nouvelle mesure électrique à 0 W.
- Une chauffe exige toujours une nouvelle mesure électrique non nulle et l'état
  natif on pour être annoncée comme observée. Les confirmations OCPP sont conservées.
- Le moteur utilise immédiatement la réservation libérée après confirmation.
- Le nouveau départ attend la temporisation native de 60 secondes, avec un
  motif explicite dans la carte, au lieu d'être envoyé trop tôt puis refusé.
- Un second clic manuel renouvelle la durée sans oublier un départ déjà autorisé
  ni déclencher un arrêt. Une pause ou une demande expirée empêche le départ.
- Pendant un arrêt préalable non confirmé, le motif devient « Chauffe demandée :
  attente de confirmation de l'arrêt précédent », afin de distinguer la demande
  utilisateur de l'ordre automatique de sécurisation.

Les corrections 0.1.4 et 0.1.5 sont incluses. Aucune migration de données, aucune
modification des limites électriques ou des accès. Aucun déploiement Portainer
ni essai physique sur le ballon n'est effectué par l'assistant.

## Mise à jour

Image cible privée Linux amd64 : `ghcr.io/macorou/solar-energy-manager:0.1.6`.
Publication et digest à consigner après validation.

Dans la Stack existante, changer uniquement `SEM_VERSION=0.1.6` si cette variable
est utilisée, ou `image: ghcr.io/macorou/solar-energy-manager:0.1.6`.
Conserver le port **8090**, le volume, le nom de Stack et les autres paramètres.
Redéployer avec téléchargement de l'image, puis actualiser complètement la page.
Le bas du menu et `/api/v1/health/live` doivent afficher **0.1.6**.

Le contrôleur conserve les résultats en attente et les réconcilie avec les
observations ; il ne les efface pas aveuglément au redémarrage. Si la demande
manuelle précédente a expiré, faire un nouvel essai « Chauffer maintenant ».
Une temporisation native peut précéder le départ. Vérifier ensuite l'état du
ballon et la montée de puissance : le bandeau vert ne prouve pas la chauffe.

Pour le fonctionnement automatique habituel, choisir **HC/HP + solaire** dans
Eau chaude → Configurer → Mode, puis enregistrer. Si un blocage persiste, relever
le motif de la carte et le bloc command de l'API ; aucune suppression du volume
ni édition manuelle de la base n'est nécessaire.

## Vérifications

Vingt-huit nouveaux cas incluent le scénario complet de reconnexion, arrêt automatique,
demande manuelle, confirmation croisée, temporisation, départ unique, second clic
et effet réellement mesuré, ainsi que les preuves manquantes/invalides et
l'annulation/expiration pendant le délai. Les cas de commande en cours d'envoi et
de zéro électrique récent contredisant l'état natif sont également couverts.

Résultats locaux : **131 tests Python réussis**, un test Docker réservé à CI ;
**20 tests UI réussis**, schéma et build TypeScript/Vite vérifiés. La revue
indépendante a relevé deux défauts importants, reproduits par huit cas RED→GREEN
puis corrigés avec une nouvelle suite complète verte. Un cas de cohérence réseau
a également été isolé pour que son refus ne repose pas sur une autre condition.
La chauffe réelle reste à valider sur l'installation.
