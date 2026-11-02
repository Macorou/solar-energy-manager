# 0.1.19 — disposition mobile et illustrations transparentes

Les cartes voiture et ballon utilisent une disposition adaptée au téléphone :
illustration et niveau dans une première ligne, puis commandes de mode, puissance
et bouton de démarrage sur toute la largeur. L’image ne déborde plus sur les
commandes. Les boutons de mode ont une hauteur minimale de 44 pixels.

Les deux illustrations disposent de véritables fonds transparents, conservés
dans les ressources PNG de l’application. Les rectangles blancs disparaissent
en thème sombre. Les carrosseries et le ballon restent blancs comme dans les
dessins d’origine. Leur préparation est documentée dans
[les notes des illustrations](../assets/device-illustrations.md).

Dans le planning mobile, le champ « Début réseau autorisé » passe sous son
libellé et occupe la largeur disponible. Les champs horaires sont explicitement
limités à la taille de leur carte, y compris leurs dimensions logiques natives.
Les horaires, jours, modes et règles de pilotage restent inchangés.

## Validation

- 77 tests de l’interface réussis et compilation de production réussie.
- 12 parcours navigateur réussis : les parcours existants sous Chromium et
  les nouveaux contrôles mobiles sous Chromium et WebKit.
- Contrôle à 320, 375, 390 et 430 pixels, en sombre et en clair : images séparées
  des commandes, champs horaires contenus et modifiables, absence de débordement.
- Vérification du canal alpha des deux fichiers et des ressources réellement
  chargées dans le navigateur ; comparaison visuelle ordinateur et téléphone.
- Revue indépendante sans problème bloquant ni modification de la régulation.

WebKit en émulation iPhone ne prouve pas le comportement du sélecteur horaire
natif sur un iPhone physique. Aucune commande n’a été envoyée à l’installation
pendant les essais.

## Mise à jour Portainer

Après réussite de la publication, utiliser :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.19
```

Ou définir `SEM_VERSION=0.1.19` si la Stack utilise cette variable. Conserver
le volume existant, les ports et les autres paramètres. Redéployer avec
téléchargement de la nouvelle image, puis actualiser complètement le navigateur.
La publication de l’image ne redéploie pas automatiquement le serveur.
