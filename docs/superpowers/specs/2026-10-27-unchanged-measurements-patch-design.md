# Patch 0.1.4 — valeurs inchangées et dernière batterie connue

Demande explicite du 27 octobre : corriger maintenant uniquement le blocage des commandes manuelles/automatiques dû à l’âge d’une valeur inchangée (ballon et voiture), et afficher le dernier SOC Peugeot connu avec sa date et « Donnée ancienne ».

## Approche retenue

Séparer l’horodatage de la valeur fournisseur de celui de sa vérification par une source disponible. La lecture réussie de l’état HA peut confirmer une puissance numérique inchangée, y compris 0 W. Garder la date fournisseur intacte et ajouter une date de vérification explicite, utilisée pour la disponibilité et la cohérence du budget. Une perte de connexion ou une valeur inconnue/invalide reste bloquante. Ne pas simplement supprimer toutes les dates ni inventer une nouvelle date de mesure.

Pour Peugeot, garder `fresh` comme information d’ancienneté et vérifier séparément la disponibilité de la dernière récupération réussie pour le pilotage automatique. Invalider le cache de pilotage après erreur fournisseur tout en conservant la valeur pour l’affichage. Respecter les objectifs SOC, l’armement, les plafonds, les temporisations et les réservations.

La confirmation physique d’une commande continue d’exiger une mesure réelle postérieure à son envoi : relire un ancien 0 W ne confirme pas un démarrage.

L’interface affiche tout SOC valide entre 0 et 100, même ancien, sa date de mesure dans le fuseau configuré et le libellé « Donnée ancienne ». Une valeur absente/invalide reste « — % ». Un ancien SOC ne devient pas un badge « En charge ».

## Périmètre

Pas de modification Ariston, de délestage par phase, de migration des réglages/identifiants, ni de commande sur l’installation pendant le développement. Publication d’une image privée Linux amd64 0.1.4 pour la Stack Portainer existante ; l’utilisateur effectue son redéploiement.

## Validation

Reproduire 0 W hier / source confirmée maintenant pour chaque appareil en manuel, solaire et heures creuses/planifié ; vérifier l’arrêt après perte de source, les valeurs invalides, les réservations et les confirmations physiques. Tester l’automatique avec SOC ancien récupéré récemment, l’objectif atteint et une erreur fournisseur. Vérifier l’affichage ancien/récent/absent/invalide sur bureau et mobile. Suite Python, tests UI, build, schémas et parcours navigateur puis revue indépendante avant publication.
