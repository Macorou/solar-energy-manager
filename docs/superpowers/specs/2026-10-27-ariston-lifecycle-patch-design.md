# Correctif du cycle de connexion Ariston

L'essai réel manuel du 27 octobre renvoie `unsupported_native_control` sur une
demande `suspend`, avec une réserve de 2570 W et un état Ariston connecté/off.
Une reproduction locale, sans réseau ni appareil, produit la même séquence :
départ refusé avant connexion, rapport de capacités vide conservé, arrêt refusé.

Le changement de mode recrée actuellement l'adaptateur et le poller à partir
de toute la configuration. Le moteur peut encore utiliser l'ancien état
connecté pendant que le nouvel adaptateur attend son initialisation.

Comportement attendu : conserver la session pour les changements de mode,
d'armement et de réglages de pilotage ; mettre sa configuration à jour ;
remplacer la session si passerelle ou identifiants changent, en invalidant
l'ancien état ; attendre l'initialisation avant l'exécution ; ne pas mémoriser
des capacités absentes avant la découverte de l'appareil.

Périmètre : backend Ariston et coordination uniquement. Préserver les corrections
0.1.4, les protections, les réservations et les confirmations électriques.
Ne pas acquitter/rejouer automatiquement une ancienne commande inconnue.
Aucun essai matériel, aucune action HA ni déploiement Portainer par l'assistant.
Distribution ciblée : image privée Linux amd64 0.1.5, sans migration de données.
