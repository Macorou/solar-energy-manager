# Mise à jour 0.1.32 — Rester connecté et gérer ses appareils

## Nouveautés

### Connexion de 30 jours glissants

Jusqu'ici, la connexion expirait 12 h après l'ouverture de session, même si SEM était utilisé entre-temps. Elle dure maintenant **30 jours après la dernière utilisation** : chaque visite repousse l'échéance. SEM enregistre ce renouvellement au plus une fois par heure, pour ne pas écrire sur le disque à chaque actualisation de l'écran.

Le cookie garde les mêmes protections : il est inaccessible aux scripts de la page et n'est pas envoyé depuis un autre site. Une session ouverte avec la 0.1.31 est prolongée dès la première visite après la mise à jour, sans nouvelle connexion.

### Réglages → Sécurité : appareils connectés

Un nouvel onglet **Sécurité** liste les appareils connectés :
- le navigateur et le système (par exemple « Chrome · Windows » ou « Safari · iPhone ») ;
- la date de connexion, la dernière activité et l'adresse IP ;
- le badge **« Cet appareil »** sur celui que l'on utilise.

Le bouton **Déconnecter** coupe immédiatement l'accès d'un appareil, et **Déconnecter les autres appareils** fait de même pour tous sauf l'appareil courant. Chaque déconnexion est écrite dans le journal, zone `auth`.

À savoir :
- Un appareil connecté avant la 0.1.32 apparaît comme « Appareil inconnu », avec la mention « Connecté avant la version 0.1.32 », tant qu'il n'est pas revenu sur SEM.
- Derrière un reverse proxy, l'adresse affichée est celle du proxy.
- Sur téléphone, les quatre onglets des Réglages tiennent sur une ligne, l'icône au-dessus du texte.

## Portainer

Utiliser SEM_VERSION=0.1.32 ou ghcr.io/macorou/solar-energy-manager:0.1.32. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3 ; la 0.1.32 ajoute seulement la table `session_info`.

**Retour en arrière :** la 0.1.31 démarre avec le même volume. Elle ignore la table `session_info` ; les sessions déjà ouvertes restent valides jusqu'à leur échéance, et les nouvelles connexions reviennent à 12 h. La sauvegarde faite avant la 0.1.31 reste nécessaire pour revenir à une version antérieure à la 0.1.31.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
