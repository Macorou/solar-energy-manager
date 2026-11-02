# 0.1.17 — réglages regroupés, planning et flux d’énergie

Cette version réunit les deux refontes graphiques approuvées :

- Choix sombre/clair en haut à droite, conservé dans le navigateur.
- Réglages regroupés en cartes avec les mesures des équipements et des sources,
  les intégrations et les fenêtres de configuration.
- Navigation Vue d’ensemble, Planning, Historique et Réglages ; les commandes
  d’activation et de vérification des appareils se trouvent dans les réglages.
- Une seule barre d’énergie : import gris, solaire consommé sur place vert,
  export jaune. Les repères de sortie représentent les consommations totales
  des appareils avec des icônes, y compris sans production solaire.
- Planning avec objectifs de charge, jours, horaires, plages d’heures creuses,
  priorités et paramètres de passages nuageux.
- Conservation des modifications locales des formulaires pendant les mises
  à jour des mesures et préservation des autres réglages lors des sauvegardes.
- Adaptation des onglets aux écrans de 320 pixels et aux polices de remplacement.

Le moteur de pilotage de la version 0.1.16 reste identique. Les commandes,
limites, confirmations, comptes et secrets persistants conservent leurs règles.
Les trois phases du réseau restent consultables dans Réglages. Le ballon garde
les modes réellement pris en charge : arrêt, solaire, heures creuses + solaire.

Les tests d’interface utilisent des données fictives ; ils n’envoient aucune
commande à l’installation. Le workflow de publication exécute les tests backend,
frontend et navigateur, puis construit et vérifie le conteneur avant publication.
La publication est confirmée uniquement lorsque ce workflow réussit.

## Mise à jour dans Portainer

Après réussite de la publication, remplacer la référence d’image par :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.17
```

Ou définir `SEM_VERSION=0.1.17` si la Stack utilise cette variable. Conserver
le volume de données existant, les ports et les autres variables. Sauvegarder
le volume avant mise à jour, puis redéployer en demandant le téléchargement
de la nouvelle image. Actualiser complètement le navigateur pour charger
l’interface compilée.

Le registre reste privé ; l’accès GHCR déjà configuré dans Portainer est utilisé.
La publication de l’image ne met pas automatiquement à jour le serveur.
