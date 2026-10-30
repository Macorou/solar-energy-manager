# 0.1.18 — affichage stable des puissances et vue d’ensemble allégée

Cette version réunit les deux correctifs demandés après la refonte graphique.

## Puissances et repères conservés entre deux relevés

- La barre conserve la dernière puissance connue de chaque appareil pendant
  l’attente du relevé suivant, même si les mesures arrivent séparément.
- Une nouvelle valeur met à jour uniquement la lecture concernée. Le repère
  d’un appareil disparaît lorsque sa propre puissance passe à 0 W.
- Une mesure manquante, ancienne ou temporairement inutilisable ne retire plus
  tous les appareils de la barre. Les watts des cartes restent aussi lisibles.
- Un relevé réseau à zéro reçu avant celui d’un appareil ne retire pas son repère.
- Un ancien relevé de secours HA ne remplace pas une observation plus récente.
  Une relecture HA récente d’un zéro inchangé reste acceptée grâce à sa date
  de vérification, même si la date de changement du capteur est ancienne.
- Une puissance estimée conserve son libellé d’estimation pendant l’attente.

La conservation se fait dans l’affichage du navigateur. Elle ne transforme pas
ces valeurs en mesures fraîches pour le moteur, les limites ou la confirmation
des commandes. Après rechargement de la page, l’interface repart des valeurs
disponibles sur le serveur. Les sources reconfigurées ne réutilisent pas le cache
de leur ancienne configuration.

## Vue d’ensemble allégée

Suppression du message de cohérence pour répartir les consommations, des phrases
sur le prix effectif et moyen de la recharge, de l’explication du mélange
réseau/solaire et du détail « effet observé » des commandes déjà confirmées.

Les puissances, l’énergie chargée, le coût de la recharge, le pourcentage solaire,
les commandes et les informations sur les commandes non résolues restent présents.
L’historique conserve les événements de confirmation.

## Mise à jour Portainer

Après réussite du workflow de publication, utiliser :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.18
```

Ou définir `SEM_VERSION=0.1.18` si la Stack utilise cette variable. Conserver
le volume existant, les ports et les autres variables ; sauvegarder le volume
avant mise à jour. Redéployer en demandant le téléchargement de la nouvelle
image, puis actualiser complètement le navigateur.

L’image reste privée et utilise l’accès GHCR déjà configuré dans Portainer.
Les tests utilisent une installation temporaire et des relevés fictifs ; ils
n’envoient aucune commande aux appareils de l’installation.
