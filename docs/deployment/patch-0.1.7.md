# Patch 0.1.7 — consignes réseau/solaire et arrêts de fin de créneau

## Changements

Les lectures de puissance Home Assistant peuvent avoir des dates fournisseur
différentes tout en ayant été vérifiées ensemble. La confirmation utilise ces
vérifications actuelles, tout en exigeant une mesure physique postérieure pour
confirmer un départ. Les arrêts Ariston conservent la confirmation native off
croisée avec la puissance. Une attente de confirmation n'est plus présentée comme
une incohérence de mesure lorsque les dernières lectures sont cohérentes.

Dans **Eau chaude → Configurer**, deux valeurs sont disponibles :

- **Consigne sur le réseau (°C)** : par exemple 55 °C, pour les HC et le manuel.
- **Consigne sur surplus solaire (°C)** : par exemple 70 °C, quand le budget
  solaire alloué couvre le ballon après marge et priorités, même pendant les HC.

La consigne existante est conservée. Sans valeur solaire différente enregistrée,
elle s'applique aussi au solaire ; la mise à jour ne relève aucune température
d'elle-même. Les valeurs doivent être acceptées par les limites natives du modèle
Ariston. La possibilité d'utiliser 70 °C dépend donc de l'appareil. Une modification
de consigne pendant une chauffe n'envoie pas un nouveau démarrage électrique et
respecte la temporisation native. La carte indique l'objectif effectif et son
origine réseau ou solaire. Les tolérances/délais de nuages existants s'appliquent
aux variations solaires. Après une perte durable du surplus, retour à la consigne
réseau si autorisée, ou arrêt ; au-dessus de la consigne réseau, la chauffe réseau
ne se prolonge pas vers la consigne solaire.

À la **fin des HC**, le ballon reçoit un arrêt explicite au premier cycle de
contrôle qui constate la fin. La voiture suit la même règle à la **fin du créneau
réseau de son planning**, dont les horaires restent indépendants des HC globales.
Le délai nuage et la durée minimale de fonctionnement ne prolongent pas ce créneau.
Une autorisation réseau encore valable dans un autre programme chevauchant est
respectée, ainsi qu'une commande manuelle temporaire explicite.

La suspension est demandée même si du solaire est disponible à cette frontière.
Une reprise solaire attend la confirmation de l'arrêt puis les délais de surplus
stable et de redémarrage. Une transition non achevée est conservée au redémarrage,
y compris si un thermostat ne consomme momentanément que 0 W. Les délais cloud et
matériel restent distincts du moment où SEM demande l'arrêt.

## Mise à jour Portainer

Image publiée : `ghcr.io/macorou/solar-energy-manager:0.1.7`, privée, Linux amd64.

Digest : `sha256:af6b4fbfaa75542b59ff61e56719782d25a79ed7ce14fe8a912cc8e48b0aaf88`.

[Publication et contrôles réussis](https://github.com/Macorou/solar-energy-manager/actions/runs/40641011085)
sur le commit `d324b6087ba8b5c9a86ae38069e9c0aad02fcbb4` : **181 tests Python**,
**22 tests UI**, **4 parcours navigateur**, schéma API/TypeScript et build,
validation Compose, construction Docker et test de démarrage/persistance/non-root.
Le workflow a vérifié la visibilité privée du paquet, le téléchargement
authentifié par digest et le refus de la demande anonyme.

Dans la **Stack existante**, modifier uniquement `SEM_VERSION=0.1.7` si cette
variable est utilisée, ou la ligne :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.7
```

Conserver **8090**, les ports OCPP existants, le volume, le nom de Stack et les
autres paramètres. Redéployer avec téléchargement de l'image, puis actualiser la
page. Le menu et `/api/v1/health/live` doivent indiquer **0.1.7**. Les données et
accès restent dans le volume existant ; ne pas le supprimer.

Ensuite, renseigner les deux consignes dans Eau chaude → Configurer. Un appareil
déjà activé peut conserver son activation pour une modification de ces seules
consignes, sous réserve de limites natives connues et compatibles. Si les limites
ne sont pas encore disponibles, utiliser **Tester la connexion**, puis enregistrer
les consignes. Un refus explicite de limites ne doit pas être contourné en
augmentant une borne arbitraire.

## Validation et limites

La revue indépendante a relevé trois cas importants : une reprise solaire
bloquée après un arrêt déjà observé, un ancien choix solaire conservé jusqu'aux
HC suivantes, et une transition pouvant se perdre entre deux écritures SQLite.
Ils ont été reproduits puis corrigés : suivi distinct de l'arrêt effectivement
émis, actualisation des temporisations solaires hors HC et sauvegarde atomique
de l'autorisation avec l'arrêt en attente. Six cas de régression supplémentaires
couvrent ces chemins, dont le parcours complet arrêt à 55 °C puis reprise solaire.

Tests locaux : **181 tests Python réussis**, un test Docker réservé à CI,
**22 tests UI réussis**, schéma et build de production vérifiés. Les mêmes suites
et les quatre parcours navigateur ont réussi sous Linux ; le test Docker
supplémentaire a réussi dans GitHub Actions.

Le suivi distingue l'arrêt de frontière d'un ancien arrêt déjà observé. Un arrêt
encore non confirmé peut être redemandé après redémarrage ; un ancien démarrage
n'est pas rejoué depuis une file persistée. L'état d'autorisation et l'arrêt à
effectuer sont enregistrés ensemble dans une écriture SQLite atomique.

La revue a laissé les observations matérielles à la mise en service, les
contrôles de distribution à la CI et les anciens sujets indépendants hors de ce
patch. Aucun point mineur différé n'a été relevé. La trace de développement a été
tenue avec les outils Windows natifs, le helper Bash étant incompatible avec les
droits de chemin de cet environnement ; cela n'affecte pas le logiciel livré.

Les essais antérieurs de démarrage/arrêt manuels et de chauffe HC ont été
confirmés par l'utilisateur avec la version 0.1.6. Les nouveaux comportements
0.1.7 sont testés avec horloge, mesures et fournisseurs simulés ; ils devront
être observés sur l'installation après mise à jour. Aucun ordre physique,
changement HA ou déploiement Portainer n'est effectué par l'assistant.
