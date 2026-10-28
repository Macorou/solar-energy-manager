# Patch 0.1.8 — consommation totale de la maison et capteur Home Assistant

## Pourquoi la carte pouvait être vide

La carte Maison calculait les autres usages en soustrayant la voiture et le
ballon. Son contrôle de cohérence utilisait les dates de publication des capteurs,
ce qui pouvait masquer des valeurs0W inchangées mais récemment vérifiées par HA.

Le choix utilisateur est maintenant appliqué : **Maison représente la consommation
totale du logement, voiture et ballon inclus**.

## Nouveau paramètre

Dans **Réglages → Home Assistant · mesures**, un champ est ajouté :

**Entité consommation totale de la maison (facultatif)**

Indiquer un capteur de **puissance totale en W ou kW**, incluant la voiture,
le ballon et toutes les phases. Un compteur cumulatif en kWh ne convient pas.
Le capteur d'échange réseau signé ne représente pas à lui seul la consommation
totale lorsque le solaire alimente aussi la maison.

Cliquer sur **Enregistrer Home Assistant**. Le jeton déjà enregistré est conservé
si son champ reste vide. Ce paramètre n'ajoute aucune entité ou automatisation HA.

- Champ renseigné : la carte utilise ce capteur, y compris lorsqu'il vaut0W.
  S'il est indisponible ou invalide, la carte affiche « — » sans changer de méthode.
- Champ vide : elle calcule **puissance réseau signée + production solaire**.
  Exemple : réseau400W + solaire0W = maison400W. La voiture et le ballon sont déjà
  inclus ; leurs puissances ne sont pas soustraites et leur indisponibilité ne
  masque pas le total. Un résultat négatif/non fini ou des lectures indisponibles
  ou incohérentes reste inconnu.

Le calcul utilise les dates de vérification HA pour les valeurs inchangées,
avec la date de mesure en repli pour les sources sans vérification. Le capteur
Maison sert à l'affichage et n'entre pas dans le budget de pilotage, les limites
ou les confirmations. Son absence ou son invalidité ne doit pas bloquer les
mesures de contrôle du ballon et de la voiture.

## Mise à jour Portainer

Image prévue : `ghcr.io/macorou/solar-energy-manager:0.1.8`, privée, Linuxamd64.
Les résultats CI et le digest seront ajoutés après vérification de la publication.

Dans la Stack existante, définir **SEM_VERSION=0.1.8** si cette variable est
utilisée, ou remplacer uniquement la version de la ligne :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.8
```

Conserver le **port8090**, le volume, le nom de Stack et les autres paramètres.
Redéployer avec téléchargement de l'image puis actualiser complètement la page.
Le menu et `/api/v1/health/live` doivent indiquer0.1.8.

Aucun capteur dédié n'est nécessaire pour essayer le calcul : laisser le nouveau
champ vide et vérifier que réseau/solaire remontent. Les accès, réglages,
consignes et activations existants sont conservés. Le patch0.1.7 est inclus.

## Validation

Préparation locale :194 tests Python et30 tests UI réussis, schéma et build
vérifiés. Les essais utilisent des sources simulées et des données temporaires.
La revue indépendante a relevé deux défauts importants : une date numérique
incorrecte pouvait interrompre la lecture et une valeur extrême en kW pouvait
empêcher la sérialisation JSON de tout l'état. Quatre régressions ont reproduit
ces cas et les attributs mal formés, puis sont passées après correction. La
normalisation vérifie aussi les valeurs après conversion des unités, et une
erreur de lecture du capteur facultatif reste isolée. Aucun point mineur différé.
Les contrôles de distribution sont confiés à la CI ; les anciennes anomalies
indépendantes restent hors de ce patch. Trace tenue avec les outils Windows natifs.
CI de publication en cours lors de la préparation du guide. Aucun déploiement
Portainer, changement HA ou ordre matériel effectué.
