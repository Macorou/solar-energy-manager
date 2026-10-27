# Installer dans Portainer

La V1 est une préversion à mettre en service sur le matériel. Les contrôles automatiques de logiciel et de conteneur ne valent pas une validation de la Wallbox, du compte Peugeot ou du NUOS.

1. Dans **Registries**, ajouter un registre personnalisé `ghcr.io`, avec le compte `Macorou` et un jeton GitHub classique autorisé sur le paquet privé, droit `read:packages`. Saisir le jeton dans Portainer uniquement. Voir la [documentation GitHub](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
2. Dans **Stacks → Add stack → Web editor**, coller le contenu du fichier `compose.yaml` du dépôt. Sélectionner le registre GHCR correspondant. Aucun `build:` ni clone local n’est requis. La Stack vise Docker Standalone Linux amd64 ; arm64 et Swarm ne sont pas encore validés.
3. Les variables facultatives sont `SEM_VERSION` (version publiée), `SEM_HTTP_PORT` (8080 par défaut), `SEM_PUBLIC_URL` (URL exacte du navigateur) et `SEM_SECURE_COOKIE` (`true` derrière HTTPS, `false` pour un premier accès HTTP sur le LAN). Une URL HTTPS publique doit utiliser des cookies sécurisés.
4. Déployer, ouvrir `http://IP_DU_SERVEUR:8080`, puis ouvrir la console du conteneur dans Portainer et lire `cat /data/bootstrap-token`. Utiliser ce code dans l’écran de première connexion et créer un mot de passe administrateur d’au moins douze caractères. Le code devient inutilisable après création du compte.
5. Dans Réglages, renseigner la limite totale et les mesures HA. Ajouter le véhicule, la borne et le ballon. Saisir les accès Peugeot/Ariston dans l’application. Tester chaque connexion. Renseigner les programmes et plages HC. Toutes les valeurs de puissance doivent correspondre à l’installation.
6. Vérifier les essais décrits dans les guides [Wallbox](wallbox-commissioning.md) et [Ariston](ariston-commissioning.md), puis confirmer l’activation de chaque appareil. Le mode reste « Arrêt » tant qu’un autre mode n’a pas été choisi. Une valeur indisponible reste inconnue.

Le même port dessert le site et OCPP : `ws://IP_DU_SERVEUR:8080/ocpp/IDENTIFIANT_BORNE`, sous-protocole `ocpp1.6`. Configurer l’identifiant, le connecteur et le mot de passe identiques des deux côtés. Utiliser WSS et un reverse proxy supportant les WebSockets hors du LAN. Ne connecter qu’un contrôleur OCPP à la borne.

Les mesures réseau et appareils doivent être rapprochées dans le temps (écart maximal de deux secondes pour une nouvelle allocation). Régler une cadence électrique adaptée, idéalement une à deux secondes, ou associer les puissances HA issues du même système de mesure. Le connecteur resynchronise les horodatages HA chaque seconde, même si les valeurs restent constantes. Lorsque les mesures ne sont pas cohérentes, le moteur conserve ou réduit une autorisation existante et attend avant de l’augmenter. Après une commande, la réservation attend aussi une mesure réseau ayant intégré son effet. Le SOC Peugeot et la température Ariston suivent leurs propres cadences cloud, plus lentes.

Le délai de confirmation physique est réglable par appareil. Pour Ariston, la fenêtre effective reste au moins égale à deux intervalles de lecture plus trente secondes ; une relecture est également demandée après une commande acceptée. Le délai ne libère pas automatiquement la puissance réservée. L’état OCPP d’attente peut fournir une puissance estimée explicitement étiquetée ; une recharge sans mesure électrique reste inconnue.

Le volume `solar_energy_data` contient base, accès chiffrés et clé. Le conteneur s’exécute sous UID/GID 10001, sans mode privilégié ni socket Docker. Un volume nommé neuf est initialisé avec les droits nécessaires. Avec un répertoire hôte, préparer ses droits pour UID 10001.

Une seule instance doit utiliser ces données. Les profils OCPP expirent et sont renouvelés pendant une autorisation valide ; leur effet hors ligne dépend de la borne et doit être testé. La santé Docker indique seulement que le service répond. Les pannes de fournisseurs restent visibles dans l’application.

Pour arrêter le pilotage d’un appareil, utiliser **Pause**, attendre sa mesure d’arrêt puis **Désactiver après arrêt**. Une déconnexion n’est jamais une confirmation d’arrêt physique. Une chauffe sanitaire imposée par le fabricant peut rester hors du contrôle du gestionnaire.

Référence : [ajouter une Stack Portainer](https://docs.portainer.io/user/docker/stacks/add).

## Mise à jour vers l’interface 0.1.2

Dans la Stack existante, définir `SEM_VERSION=0.1.2` si cette variable est utilisée, ou remplacer la référence de l’image par `ghcr.io/macorou/solar-energy-manager:0.1.2`. Le Compose courant utilise 0.1.2 par défaut. Redéployer en demandant le téléchargement de la nouvelle image ; conserver le volume existant, les ports, l’URL publique et les cookies déjà configurés. Une actualisation complète du navigateur recharge les nouveaux fichiers de l’interface.

Le correctif conserve le format de données et les connexions. Il restaure la composition du concept initial et corrige la reprise du mode Automatique ainsi que les légendes des programmes passant minuit. Les essais matériels de première mise en service restent nécessaires s’ils n’ont pas encore été réalisés.
