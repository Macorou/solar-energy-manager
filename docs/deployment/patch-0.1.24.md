# Mise à jour 0.1.24 — Écritures disque réduites et journaux conservés plus longtemps

La boucle de pilotage (toutes les 2 secondes) réécrivait à chaque passage l’état complet des sessions de charge, y compris des tampons qui grossissaient pendant toute la durée du branchement. Après une longue charge, plusieurs centaines de Mo par heure étaient écrits dans `app.db`, même voiture débranchée. Les valeurs d’exécution identiques ne sont plus réécrites, les tampons de session sont bornés, et l’enregistrement d’une session est immédiat pour tout changement de comptage (compteur, SOC, branchement, tarif) mais limité à une fois par minute quand seuls les compteurs de temps avancent.

Mesure synthétique (base jetable, données fictives, 6 h de charge puis 1 h débranchée) : 329 Mo écrits pendant la sixième heure de charge avec 0.1.23, 6 Mo avec 0.1.24 ; 359 Mo pendant l’heure débranchée, 0,04 Mo désormais. L’effet réel dépend de l’installation et reste à observer.

En cas d’arrêt brutal du conteneur, jusqu’à une minute de durée de charge peut manquer : la durée de la session est alors marquée partielle, comme pour toute interruption de suivi. L’énergie, le coût et le SOC ne sont pas concernés.

## Journaux

Les traces périodiques partageaient la limite de 10 000 lignes avec les erreurs et la remplissaient en quelques heures. La conservation reste de 7 jours, avec deux budgets séparés : 10 000 lignes INFO, WARN, ERROR et FATAL, et 60 000 lignes DEBUG et TRACE (environ une journée de détail, selon le trafic). La trace du site est écrite toutes les 30 secondes et immédiatement lorsqu’une décision d’appareil change ; la lecture Home Assistant réussie est notée une fois par minute. Le téléchargement inclut toutes les lignes conservées.

Un index est ajouté à la table `diagnostic_logs`. Le schéma SQLite reste en version 3 : un retour à l’image 0.1.23 reste possible avec le même volume.

## Portainer

Utiliser SEM_VERSION=0.1.24 ou ghcr.io/macorou/solar-energy-manager:0.1.24, télécharger la nouvelle image et conserver le volume /data et les ports existants. Après une journée de fonctionnement, la page Journaux doit encore afficher des lignes DEBUG/TRACE de la veille.

Aucune commande matérielle n’a été envoyée pendant le développement. Les essais utilisent un stockage et des transports de test ; aucun historique, accès ni réglage de l’installation réelle n’a été modifié par ces tests.
