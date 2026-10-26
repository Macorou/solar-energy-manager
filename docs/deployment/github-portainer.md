# Dépôt privé, images GHCR et Portainer

Statut : stratégie de livraison validée ; image et Compose à produire pendant le développement. Aucune commande de déploiement présentée ici ne signifie qu’une image existe déjà.

## Emplacements

- Dépôt privé : https://github.com/Macorou/solar-energy-manager
- Image cible : `ghcr.io/macorou/solar-energy-manager`
- Version et digest : à renseigner uniquement après publication et vérification effectives.
- Fichier de déploiement prévu : `compose.yaml`, sans construction requise dans Portainer.

## Chaîne de livraison prévue

1. Développer et tester une étape dans le dépôt privé.
2. Exécuter les vérifications backend, interface et conteneur dans GitHub Actions.
3. Pour une version approuvée, construire et publier l’image avec le `GITHUB_TOKEN` du workflow et le droit `packages: write`.
4. Vérifier que le paquet GHCR est privé, lié au dépôt et téléchargeable avec un accès autorisé.
5. Référencer la version ou le digest vérifié dans le Compose.
6. Déployer cette image depuis une Stack Portainer avec son volume de données.

Les pull requests ne publient pas d’image. L’utilisation d’un tag de version ou d’un digest permet de choisir la version installée au lieu de suivre implicitement une référence mouvante.

## Accès de Portainer à une image privée

Portainer doit disposer d’un registre configuré vers `ghcr.io`, du compte autorisé et d’un accès en lecture au paquet. GitHub documente actuellement l’authentification d’un client externe à GitHub Packages par un jeton personnel classique ; pour télécharger une image, le droit pertinent est `read:packages`, avec accès effectif au paquet privé.

Ce secret se saisit dans la configuration du registre de Portainer. Il ne doit figurer ni dans le Compose, ni dans une capture partagée, ni dans les sources. Aucun jeton personnel de publication n’est nécessaire dans le dépôt : le workflow utilise son jeton GitHub Actions propre.

La visibilité du dépôt source et celle du paquet sont deux paramètres à vérifier. Aucun changement vers une visibilité publique n’est prévu.

## Première livraison et exploitation

La livraison fournira l’URL du workflow réussi, la version réellement publiée, son digest, le Compose, les ports utilisés et la procédure de première connexion. La configuration de l’application sera stockée dans un volume persistant ; les plages HC/HP ne dépendront pas de Home Assistant.

Le guide de mise à jour et de sauvegarde sera complété avec le format de base réel. Une restauration nécessite une sauvegarde cohérente et la clé de protection des accès. Les essais Portainer et matériels seront consignés séparément des tests simulés.

## Documentation de référence

- [GitHub Container Registry : accès, visibilité et publication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [GitHub Actions : publication d’images Docker](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
- [Portainer : création d’une Stack](https://docs.portainer.io/user/docker/stacks/add)
