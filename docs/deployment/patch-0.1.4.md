# Patch 0.1.4 — valeurs inchangées et batterie connue

## Modifications

- Une puissance numérique disponible, relue avec succès dans Home Assistant, reste utilisable même si son horodatage de valeur est ancien. Cela corrige notamment un ballon ou une voiture à 0 W depuis la veille, en manuel comme en automatique.
- La date fournisseur `measured_at` est conservée. Le champ `checked_at` indique séparément la dernière vérification de l’état auprès de HA ; il sert au contrôle de disponibilité et au budget.
- Une valeur inconnue/invalide, une perte de connexion ou l’absence de nouvelle vérification de la source restent bloquantes. Une lecture HTTP confirme la valeur publiée par HA, pas une nouvelle mesure physique du compteur : HA doit signaler correctement l’indisponibilité de ses capteurs.
- Un SOC Peugeot valide récupéré récemment reste utilisable même si sa date de mesure est ancienne. Une erreur de connexion fournisseur empêche le pilotage automatique sur ce cache jusqu’à la prochaine récupération réussie.
- La voiture affiche le dernier SOC valide connu, y compris 0 %, avec sa date de mesure dans le fuseau configuré. La mention « Donnée ancienne » distingue les valeurs anciennes. Une valeur absente/invalide reste « — % ».
- Les limites électriques, priorités, objectifs de charge, armement, temporisations et réservations restent appliqués. Les confirmations physiques continuent d’exiger des observations postérieures à la commande ; une ancienne valeur relue ne prouve pas une chauffe ou une recharge.

Pas de changement des connecteurs Ariston/OCPP, du graphisme, des identifiants enregistrés ou du format de stockage. Aucun délestage par phase ajouté dans ce patch.

## Mise à jour de la Stack existante

Image prévue : `ghcr.io/macorou/solar-energy-manager:0.1.4`, Linux amd64. Vérifier la réussite du workflow de publication avant de la sélectionner.

Dans Portainer, conserver le nom de la Stack, le volume de données, le port existant 8090 et les autres variables. Modifier uniquement `SEM_VERSION=0.1.4` si cette variable est utilisée, ou l’image en `ghcr.io/macorou/solar-energy-manager:0.1.4`. Redéployer avec téléchargement de l’image, puis actualiser complètement le navigateur. Les accès et réglages restent dans le volume existant.

Pour le premier essai, annuler une ancienne demande manuelle restée en attente avant de redéployer. Une nouvelle demande et l’observation de son effet servent à valider le fonctionnement sur l’installation ; les tests logiciels ne remplacent pas cet essai.

Retour possible à l’image 0.1.3 avec le même volume ; aucune migration de base n’est introduite.
