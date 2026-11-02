# Mise à jour 0.1.26 — Surplus solaire au-delà de l’objectif de la voiture

Jusqu’ici, la voiture s’arrêtait à son objectif (celui du programme ou l’objectif habituel) même lorsqu’il restait du surplus solaire. Un nouveau réglage de la borne, « Objectif sur surplus solaire (%) », permet de continuer avec le surplus seul.

- Sous l’objectif : rien ne change, le réseau charge pendant le créneau et le solaire autour.
- Entre l’objectif et l’objectif sur surplus : seul le surplus solaire charge la voiture, même pendant un créneau réseau. La nuit, la charge s’arrête donc toujours à l’objectif. La raison affichée est « Surplus solaire au-delà de l’objectif, jusqu’à N % ».
- À l’objectif sur surplus : « Objectif atteint ». À 100 %, c’est la voiture qui termine la charge ; le surplus revient alors au ballon.
- Le mode Manuel n’est pas concerné et s’arrête à l’objectif habituel.
- Champ vide (valeur par défaut) : comportement identique à 0.1.25.

La carte de la voiture affiche « surplus jusqu’à N % » après l’objectif. Le champ « Objectif solaire habituel » est renommé « Objectif habituel » : il sert hors programme et en mode Manuel.

Une charge déjà terminée est relancée par SEM : le courant est relevé si la session de la borne est ouverte, sinon une nouvelle session est démarrée. La reprise dépend ensuite de la voiture.

## Portainer

Sauvegarder le volume /data, puis utiliser SEM_VERSION=0.1.26 ou ghcr.io/macorou/solar-energy-manager:0.1.26, télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3 et aucun nouveau champ de réglage n’est ajouté : un retour à 0.1.25 reste possible avec le même volume (l’objectif sur surplus y est simplement ignoré).

Après la mise à jour, renseigner si souhaité l’objectif sur surplus (par exemple 100 %) dans Appareils → borne.

Aucune commande matérielle n’a été envoyée pendant le développement. Les essais utilisent un stockage et des transports de test ; aucun historique, accès ni réglage de l’installation réelle n’a été modifié par ces tests.
