# Revue de la V1 et décisions d’exécution

Revue indépendante du code à `447290891a9a5d592fd81573b643f266ca915530`, puis une passe de corrections avec tests de non-régression. Le réviseur n’a pas modifié le checkout. Aucun point mineur n’a été différé.

| Point confirmé par la revue | Correction et preuve |
| --- | --- |
| Arrêt perdu pendant un démarrage en cours | File persistée par appareil, arrêts prioritaires et envoi sérialisé ; test pause pendant une réponse retardée. |
| Réservation d’un appareil moins prioritaire réutilisée | Toutes les puissances engagées sont réservées avant l’allocation ; variantes réseau et solaire testées. |
| Démarrages OCPP répétés avant notification de transaction | État de démarrage en attente persisté ; changements de limite indépendants ; notification arrivant avant réponse également testée. |
| Délai de confirmation Ariston inférieur au polling | Délai réglable, plancher adapté à la cadence, relecture après commande ; conservation de la réservation au-delà de 91 secondes testée. |
| Mesures prises de part et d’autre d’une transition | Cohérence temporelle du bilan, blocage des augmentations et réconciliation après intégration réseau ; deux ordres de réception testés. |
| Création d’identifiants incompatible avec HTTP LAN | Générateur utilisant getRandomValues si randomUUID est absent ; test navigateur sur origine HTTP d’adresse IP. |
| Rafraîchissement HA repoussé par des événements sans rapport | Échéance monotone indépendante des messages ; test de flux continu d’une autre entité. |

Les estimations d’attente OCPP sont explicitement étiquetées dans l’API et l’interface. Une recharge sans mesure reste inconnue. Les affichages de puissance ignorent les valeurs inutilisables. Les cas sont d’abord passés en échec, puis en réussite après correction.

## Décisions prises pendant l’exécution

1. Le chat sans projet ne permettait pas au gestionnaire natif de sélectionner le dépôt imbriqué : création du worktree Git par CLI, après choix explicite de l’utilisateur. Coût : cycle de vie local à gérer par Git.
2. Les scripts de suivi Bash échouaient sur les chemins Windows : suivi équivalent en Python/PowerShell, avec bases Git et résultats conservés. Coût : automatisation du skill remplacée par un équivalent natif.
3. `uv` absent : environnement Python dédié, dépendances figées, mêmes tests repris sous Linux en CI. Coût : commandes locales différentes, compatibilité contrôlée par la CI.
4. Tests navigateur placés dans `frontend/tests/e2e` pour la résolution npm ; types générés depuis OpenAPI et versionnés. Coût : chemins différents du plan, sans changement fonctionnel.
5. Documentation de livraison préparée pendant l’attente de la CI. Le serveur est confirmé Intel/AMD64. Aucun accès Portainer n’est supposé disponible. Coût : le déploiement de l’installation reste à effectuer.
6. Le champ repository n’est pas fourni dans la réponse REST du conteneur : vérification par visibilité privée, téléchargement authentifié du digest, refus anonyme et label OCI de source. Coût : l’association visible sur la page du paquet n’est pas affirmée par cette API ; le téléchargement et la provenance restent vérifiés.

## Points hors des essais disponibles

- Wallbox/NUOS physiques, limites réelles et repli hors ligne : restent à tester avant activation ; risque de compatibilité matérielle encore ouvert.
- Compte Peugeot et fraîcheur réelle de cette e-208 : restent à connecter et comparer ; objectif de SOC non garanti sans ces données.
- Récupération privée depuis le Portainer de l’utilisateur : image et accès CI distingués de cet essai ; configuration du registre encore nécessaire côté serveur.
- Intégration de retour HA et Tempo : extensions explicitement différées après la base ; aucune fonction de ce type n’est annoncée active.
