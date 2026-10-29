# Peugeot : récupération du SoC et estimation dans EVCC

Analyse du 29 octobre 2026, sur le checkout EVCC propre à la référence
`9404d825d6a659d8ce7f47d3b0d2e14ac04506e0` du 28 octobre 2026.
Complément de `2026-10-29-evcc-charging-engine.md`.

Note rédigée avant implémentation. Le port est réalisé pour 0.1.15 ; voir
`../deployment/patch-0.1.15.md`. Les vecteurs EVCC adaptés ont été exécutés
en Python ; la suite Go amont n'a pas été exécutée.

## Décision utilisateur : reprendre l'estimateur EVCC sans dates Peugeot

L'utilisateur a explicitement demandé de reprendre le fonctionnement et le code
EVCC pour l'estimation, y compris son choix de ne pas utiliser la date Peugeot.
Cette décision remplace la précédente proposition de recalage daté de SEM.

Le port devra suivre `core/soc/estimator.go` :

- même pourcentage reçu : poursuivre l'estimation depuis l'énergie chargée ;
- pourcentage différent : adopter cette valeur et le niveau d'énergie courant
  comme nouvelle référence, même si le pourcentage baisse ;
- aucune réponse : poursuivre depuis le dernier point valide lorsque possible ;
- rendement initial EVCC de 85 %, puis apprentissage de son gradient selon les
  mêmes conditions ; l'ancien rendement fixe SEM ne pilote plus cet estimateur ;
- règles EVCC en cas de remise à zéro de l'énergie, avec les tests correspondants ;
- pourcentage effectif estimé utilisé par le moteur pour atteindre l'objectif.

La date de mesure Peugeot ne décidera plus de l'adoption, du rejet, du recalage
ou de la validité du pourcentage pour le pilotage. Une réponse dont le pourcentage
change sera traitée comme le fait EVCC, sans arbitrage chronologique ajouté.
Une même valeur retournée avec une nouvelle date ne remettra pas l'estimation à
zéro. Cette décision concerne les relevés Peugeot ; les dates des mesures
électriques et les horaires des plannings gardent leurs responsabilités propres.

Cette note rapporte une lecture des sources et des tests. Les tests Go n'ont pas
été exécutés pour cette analyse. Aucun appel à la voiture, à Peugeot, à Home
Assistant ou à la borne n'a été effectué.

## Chemin de récupération

1. `vehicle/psa.go` enregistre Peugeot avec le realm `clientsB2CPeugeot`, construit
   une identité OAuth depuis les tokens, sélectionne le véhicule par VIN et crée
   un fournisseur PSA avec cache.
2. `vehicle/psa/api.go` lit le statut par GET sur
   `https://api.groupe-psa.com/connectedcar/v4/user/vehicles/<id>/status`, via un
   transport OAuth. La lecture de statut ne contient pas de commande de réveil ou
   de demande de remontée du véhicule.
3. `vehicle/psa/provider.go`, `Soc()`, sélectionne l'entrée `Energy` de type
   `Electric` et retourne son champ `Level`. La même réponse fournit autonomie,
   état de connexion/charge et autres informations.
4. Le template `templates/definition/vehicle/peugeot.yaml` configure un cache de
   15 minutes par défaut. Il est modifiable. Pendant la charge, le loadpoint peut
   appeler le fournisseur à chaque cycle, sans provoquer autant de requêtes
   réseau puisque `util.Cached` réutilise sa réponse jusqu'à expiration. Un cycle
   sans nouvelle requête n'est pas une nouvelle mesure physique.
5. `publishSocAndRange` de `core/loadpoint.go` essaie d'abord un SoC fourni par la
   borne, puis celui du véhicule lorsque son interrogation est autorisée. Il
   transmet le résultat, ou l'absence de résultat, à l'estimateur avec l'énergie
   chargée. Une capacité positive active cet estimateur par défaut, sauf option
   `soc.estimate: false` ; voir `core/loadpoint_vehicle.go`.

Le fournisseur PSA possède bien un champ `UpdatedAt` dans le type `Energy`, mais
`Provider.Soc()` ne le transmet pas à l'estimateur et n'y applique pas de filtre
d'ancienneté. Ce point distingue le code EVCC étudié du suivi daté de SEM.

## Fonctionnement exact de l'estimateur

Source : `core/soc/estimator.go`, constructeur `NewEstimator` et méthode `Soc`.

L'estimateur mémorise un pourcentage véhicule de référence et l'énergie chargée
au moment où il adopte cette référence. Son gradient initial est :

```
Wh nécessaires pour +1 % = capacité configurée en Wh / 0,85 / 100
SoC estimé = SoC de référence + énergie supplémentaire / gradient
```

Le rendement initial est donc de 85 %. Le SoC est plafonné à 100 %. Ce calcul
utilise l'énergie chargée en Wh, pas une intégration du pourcentage déjà estimé.

### Premier relevé valide

EVCC adopte le pourcentage et l'énergie courante comme point de référence. Il
n'ajoute pas l'énergie déjà chargée avant l'arrivée de ce premier relevé.
`TestMissingSocFromZero` vérifie aussi que 0 % constitue une référence valide.

### Peugeot renvoie le même pourcentage

Lorsque le pourcentage retourné est identique au dernier pourcentage véhicule
mémorisé, et que le compteur ne s'est pas réinitialisé, EVCC poursuit
l'interpolation depuis ce point de référence. Une répétition de 60 % ne remet
donc pas un affichage estimé à 68,5 % à 60 %.

La date du relevé ne participe pas à ce choix : la méthode `Soc` reçoit seulement
un pourcentage optionnel et une énergie. Même un relevé plus récent indiquant le
même pourcentage suit cette branche.

### Peugeot renvoie un pourcentage différent

EVCC adopte exactement ce pourcentage et recale la référence d'énergie au niveau
actuel. La correction peut monter ou descendre par rapport à l'estimation.
Le supplément d'énergie déjà utilisé dans l'ancienne estimation n'est pas ajouté
une seconde fois après cette correction.

Il n'y a pas de comparaison des dates Peugeot dans cette méthode : une réponse
différente est traitée comme une nouvelle référence. Le port demandé reprendra
ce comportement, sans filtre chronologique supplémentaire.

### Aucune réponse Peugeot / interrogation non effectuée

Après un premier relevé valide, EVCC continue l'extrapolation depuis l'énergie.
Dans cette branche, il conserve au moins l'estimation déjà obtenue et n'applique
pas de delta d'énergie négatif. Sans premier relevé valide, il ne peut pas déduire
un pourcentage absolu de la seule énergie chargée.

### Compteur remis à zéro

Avec un pourcentage véhicule disponible et un delta d'énergie négatif, la méthode
repasse par le chemin d'adoption de référence. Sans pourcentage disponible, elle
conserve l'estimation et n'invente pas un gain depuis un delta négatif. Les tests
`TestMissingSoc` vérifient ces cas. Une adaptation doit coordonner ce comportement
avec les changements de transaction et la persistance des sessions de SEM.

### Apprentissage du gradient

Quand l'écart entre le SoC constructeur adopté et le premier SoC de référence
dépasse 10 points, avec une énergie positive correspondante, EVCC recalcule les
Wh nécessaires par point de pourcentage. Il affine donc le gradient d'estimation
depuis les observations, au lieu d'appliquer indéfiniment le rendement initial.
Cette condition utilise les références internes de l'estimateur ; ce n'est pas
un calcul fondé sur une mesure directe de l'énergie dans la batterie.

## Exemple numérique

Pour une capacité configurée à 50 kWh, avec le gradient initial à 85 % :

| Événement | Énergie depuis le début | SoC utilisé |
| --- | --- | --- |
| Premier relevé Peugeot : 60 % | 0 kWh | 60 % |
| Peugeot répète 60 % | 5 kWh | 68,5 % estimés |
| Peugeot retourne 66 % | 5 kWh | 66 %, nouvelle référence |
| Peugeot répète 66 %, puis 1 kWh supplémentaire est chargé | 6 kWh | 67,7 % estimés |

La différence entre la date de mesure et la date de réception n'est pas
représentée dans cet exemple : EVCC recale ici au moment où il reçoit/adopte la
valeur. C'est également le comportement demandé pour SEM ; aucun index passé
ne sera recherché à partir de la date du relevé Peugeot.

## Le pourcentage utilisé pour arrêter

`publishSocAndRange` affecte le résultat de l'estimateur à `vehicleSoc`.
`LimitSocReached` compare ce `vehicleSoc` à l'objectif effectif de session ; la
stratégie peut alors suspendre la charge. L'estimation participe donc au
pilotage, et pas seulement à l'affichage. La stratégie de planning dispose aussi
de son propre objectif effectif et des priorités décrites dans l'analyse du
moteur ; toutes les limites ne se résument pas à la seule limite de session.

## Conséquences pour la refonte de SEM

Le suivi actuel `backend/app/runtime/charging.py` conserve une référence
Peugeot persistante par véhicule/VIN, utilise l'énergie OCPP et un rendement
configurable, puis remplace la référence sur un relevé daté plus récent. Ces
choix d'estimation doivent être remplacés par le comportement EVCC demandé.
L'historique des sessions, de l'énergie et des coûts devra être conservé lors de
cette migration ; il ne constitue pas une autorisation de conserver les anciennes
règles de recalage du SoC.

Les points à inclure dans la conception sont :

- adopter automatiquement une valeur Peugeot valide selon les règles EVCC,
  sans confirmation manuelle de pourcentage et sans sélection par date ;
- poursuivre l'estimation entre les relevés sans réinitialiser les gains sur
  chaque répétition de la même réponse ;
- distinguer un pourcentage identique, un pourcentage différent et une erreur
  de connexion, exactement comme l'estimateur EVCC ;
- recaler l'énergie de référence au niveau courant sans double comptage, sans
  interpolation à la date du relevé Peugeot ;
- reprendre le rendement initial de 85 % et l'apprentissage du gradient EVCC ;
- utiliser le même SoC effectif pour la progression et l'objectif de recharge,
  tout en affichant distinctement le relevé Peugeot et l'estimation ;
- préserver les références et les index entre suspension, reprise et reboot,
  avec les contrôles des compteurs et de l'identité véhicule.

Cas de référence à reprendre : `TestSocEstimation`, `TestMissingSoc`,
`TestMissingSocFromZero` de `core/soc/estimator_test.go`, auxquels ajouter la
persistance propre à SEM et des tests démontrant que changer ou supprimer la date
Peugeot ne modifie pas les résultats de l'estimateur. Ces tests ont été inspectés, sans être
exécutés dans cette phase d'analyse.

## Sources figées

- [Fournisseur PSA](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/vehicle/psa/provider.go)
- [API PSA](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/vehicle/psa/api.go)
- [Configuration Peugeot](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/templates/definition/vehicle/peugeot.yaml)
- [Estimateur et tests](https://github.com/evcc-io/evcc/tree/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/soc)
- [Publication du SoC et contrôle de charge](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/loadpoint.go)
- [Interrogation et association du véhicule](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/loadpoint_vehicle.go)
