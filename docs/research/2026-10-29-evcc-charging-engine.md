# Analyse du moteur de recharge EVCC

Date : 29 octobre 2026. Note de recherche rédigée avant le port. Le choix du
port Python a ensuite été approuvé et mis en œuvre pour la version 0.1.15 ;
voir `../deployment/patch-0.1.15.md` pour le comportement livré et ses limites.
Les formulations prospectives ci-dessous décrivent cette phase de recherche.

## Référence reproductible

Le dépôt public EVCC a été cloné intégralement, avec un historique limité au
dernier commit, dans `work/evcc-reference` du dossier de travail local. Le checkout
est propre. La référence étudiée est
[`9404d825d6a659d8ce7f47d3b0d2e14ac04506e0`](https://github.com/evcc-io/evcc/tree/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0),
datée du 28 octobre 2026 à 12:32:58 +01:00. Les liens ci-dessous sont figés sur ce
commit ; les pages de documentation peuvent évoluer.

Le code est sous licence MIT, avec copyright evcc.io (andig, naltatis,
premultiply). La notice `docs/third-party/evcc-MIT.txt` a été étendue aux
algorithmes, profils, mesures et tests adaptés pour 0.1.15 ; elle est conservée
dans les sources et l'image Docker.

Les sources et tests ont été lus ; la suite de tests Go EVCC n'a pas été exécutée.
Aucune commande n'a été envoyée à la borne ou au ballon pendant cette analyse.

## Ce que fait réellement EVCC

### 1. Une boucle de régulation complète

[`core/site.go`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/site.go)
enchaîne la lecture des compteurs des points de charge, la mise à jour des
circuits, les compteurs du site, le bilan de puissance et la régulation du point
de charge sélectionné. Des événements peuvent déclencher une mise à jour en plus
du cycle périodique. `Run` avertit explicitement qu'un intervalle inférieur à
30 secondes peut produire des oscillations. Il ne s'agit donc pas de recalculer
une nouvelle soustraction toutes les deux secondes sur les mêmes mesures.

Les responsabilités sont distinctes : autoriser une recharge selon le mode,
calculer son courant souhaité, le plafonner par les circuits, puis appliquer et
synchroniser la consigne de la borne. Un accusé de réception OCPP, un courant
offert et un courant consommé ne désignent pas le même état.

### 2. Calcul du courant solaire

Dans
[`core/loadpoint.go`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/loadpoint.go),
`pvMaxCurrent` convertit le bilan réseau signé en variation de courant :

```
variation A = -puissance_site W / (230 V × phases actives)
courant souhaité = max(0, courant effectif + variation A)
```

Le courant effectif vaut zéro si le véhicule ne charge pas. S'il charge et que
les courants sont disponibles, `effectiveCurrent` utilise le maximum des
courants mesurés, majoré de 2 A, plafonné par le courant offert. Cette correction
concerne la régulation solaire ; la validation électrique du circuit utilise le
courant réel sans cette majoration.

Le résultat est borné par les courants minimal et maximal effectifs, issus de la
configuration, du véhicule et des capacités déclarées de la borne. EVCC arrondit
aux ampères entiers uniquement si le véhicule ou le connecteur l'exige. Son
connecteur OCPP sait envoyer des dixièmes d'ampère.

### 3. Temporisations solaires

EVCC utilise une temporisation de démarrage lorsque le surplus couvre le seuil
minimal, puis démarre au courant minimal. Le cycle suivant ajuste la puissance.
Lorsque le surplus devient insuffisant, il réduit le courant jusqu'au minimum
et applique la temporisation d'arrêt solaire. Le retour du surplus réinitialise
cette temporisation. Les valeurs initiales du noyau sont 60 secondes au démarrage
et 180 secondes à l'arrêt ; des paramètres les remplacent.

Ces temporisations ne retardent pas la validation d'un circuit surchargé, une
pause explicite ou un objectif atteint. Les transitions de mode/planning de SEM
doivent également conserver leur arrêt immédiat demandé par l'utilisateur.

### 4. Limitation électrique : courant réel et marge du circuit

[`core/circuit/circuit.go`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/circuit/circuit.go)
contient `ValidateCurrent` et `ValidatePower`. Pour un circuit limité :

```
marge = limite du circuit - charge mesurée du circuit
variation demandée = max(0, nouvelle demande - consommation réelle du véhicule)
si variation demandée > marge :
    demande autorisée = min(demande, max(0, consommation réelle + marge))
```

Les validations remontent ensuite les circuits parents. Une limite de puissance
totale est indépendante de la limite en ampères et peut encore réduire le
résultat. `setLimit` du loadpoint utilise `actualMaxChargeCurrent` et la puissance
réellement consommée pour ces deux contrôles. Le courant offert ne sert de
repli que lorsque le véhicule charge et que les courants ne sont pas mesurables.

Point essentiel : avec les mêmes mesures, refaire ce calcul donne la même
consigne. On ne retire pas de nouveau le même dépassement à la dernière
consigne envoyée.

Dans le circuit triphasé standard EVCC, la grandeur de courant retenue est le
maximum des trois courants signés ; les puissances par phase peuvent fournir le
signe. Cette représentation scalaire est conservatrice pour une voiture
monophasée si une autre phase est chargée. SEM a déjà une correspondance physique
des phases par borne et des limites L1/L2/L3 distinctes. La porter explicitement
est une adaptation, à tester comme telle, et non une fonctionnalité à attribuer
à tort au `ValidateCurrent` scalaire EVCC.

Un circuit sans compteur additionne ses charges. Un circuit avec compteur se
base sur ce compteur, donc tient compte des autres usages de la maison. Sur une
erreur de lecture, EVCC conserve temporairement la dernière valeur puis force une
limitation après le délai configuré, une minute par défaut.

### 5. Réduire avant de suspendre

`setLimit` applique le courant calculé avec `MaxCurrentMillis`/`MaxCurrent`. Il
n'envoie pas un arrêt à chaque dépassement. La borne reste autorisée si le courant
retenu couvre le minimum de recharge, normalement 6 A.

Si le résultat descend sous le minimum, EVCC peut suspendre. Il conserve toutefois
6 A pour une voiture déjà en charge mesurant légèrement moins de 6 A lorsque le
circuit est rempli mais pas réellement surchargé. Le test
[`core/loadpoint_circuit_test.go`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/loadpoint_circuit_test.go)
couvre précisément 5,9 A mesurés pour 6 A offerts, avec et sans dépassement.

EVCC n'offre donc pas une garantie de recharge ininterrompue si les autres usages
ne laissent même plus 6 A disponibles. La suspension reste nécessaire dans ce cas.

### 6. Application et synchronisation de la consigne

Le courant offert interne est mis à jour après réussite de la commande. L'état
autorisé est séparé du courant et de l'état physique du véhicule. `syncCharger`
compare ensuite l'état de la borne, le courant offert, le courant mesuré et la
consigne attendue. Une période de stabilisation de 60 secondes après changement
d'autorisation tolère des désaccords transitoires.

Un écart entre courant offert et courant consommé est une information à
diagnostiquer ; il ne transforme pas automatiquement toutes les commandes en
résultat inconnu et ne bloque pas tous les appareils du site.

Les statuts OCPP sont traduits par
[`charger/ocpp.go`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/charger/ocpp.go)
en A (absent), B (branché sans charge) et C (en charge), avec une raison
supplémentaire pour l'authentification attendue et le débranchement requis.

### 7. OCPP : suspension par profil, paramètres Wallbox

Le connecteur EVCC générique modifie un profil de courant. `Enable(false)`
applique 0 A, ce qui permet de suspendre la fourniture tout en conservant une
transaction OCPP. `Enable(true)` réapplique le courant. Ce mécanisme diffère du
`RemoteStopTransaction` systématique actuellement utilisé par SEM.

Le profil par défaut est `TxDefaultProfile`. `TxProfile` est une option explicite,
avec gestion de la récupération et du changement d'identifiant de transaction.
Les profils EVCC étudiés ne possèdent pas l'expiration de 90 secondes de SEM.
Il faut traiter cette différence de politique hors ligne dans la conception :
une expiration de profil positif ne garantit pas, à elle seule, un arrêt ; la
borne peut retomber sur un autre profil ou sa limite propre.

Le profil courant Wallbox
[`ocpp-wallbox.yaml`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/templates/definition/charger/ocpp-wallbox.yaml)
impose `profilekindrelative: true`. Le profil dédié
[`ocpp-wallbox-fw5.yaml`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/templates/definition/charger/ocpp-wallbox-fw5.yaml)
impose au contraire le démarrage distant et le niveau de pile zéro, et écarte
`Current.Offered` et `Power.Offered`. Il ne faut pas mélanger ces deux variantes
sans connaître le firmware réel. Les deux templates signalent que les mesures
OCPP Wallbox peuvent être incomplètes et que la connexion peut être instable.

EVCC découvre également les unités supportées, les niveaux de pile et les
capacités de mesure dans `charger/ocpp/cp_setup.go`. Il négocie les mesures
acceptées et ne présume pas que tous les champs sont disponibles.

### 8. Mesures, transactions et reconnexion

[`charger/ocpp/connector_core.go`](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/charger/ocpp/connector_core.go)
et `connector.go` distinguent :

- la date de mesure fournie par la borne, pour ordonner les échantillons ;
- la date locale de réception, pour le délai d'indisponibilité ;
- les index de début/fin de transaction et les valeurs périodiques courantes.

À date égale, une valeur périodique prime sur un contexte `Transaction.Begin` ou
`Transaction.End`, quel que soit l'ordre des champs dans le message. Une valeur
ancienne ne remplace pas une valeur plus récente. Les courants et puissances
retombent à zéro sur fin de transaction, tandis que l'index d'énergie est conservé.
Une transaction en cours peut être récupérée depuis les `MeterValues` après
reconnexion. Un simple reconnect n'est pas un nouveau branchement de voiture.

Les tests `TestOnMeterValuesLaggingTimestamp`, `TestOnMeterValuesBoundaryContext*`,
`TestOnStopTransactionResetsReportedPower` et `TestOnBootNotification*` fournissent
des cas de référence directement réutilisables pour l'adaptation.

### 9. Batterie, énergie et plannings

`core/soc/estimator.go` extrapole le SoC depuis un premier relevé véhicule et
l'énergie chargée, puis prend en compte les nouvelles valeurs du véhicule.
Son rendement initial est 85 %, avec adaptation de la pente. SEM possède déjà
un suivi persistant et un rendement configurable. Après l'analyse, l'utilisateur
a explicitement demandé de remplacer aussi son estimation par le code et les
règles EVCC, sans sélection ou recalage fondés sur la date Peugeot : rendement
initial de 85 %, apprentissage du gradient, poursuite sur pourcentage identique,
adoption d'une valeur différente à l'énergie courante. Voir l'analyse dédiée
`2026-10-29-evcc-peugeot-soc.md`. L'historique des sessions, l'arrêt à l'objectif,
l'énergie chargée, le coût et la part solaire doivent être conservés.

EVCC peut calculer le démarrage nécessaire pour une échéance en fonction de la
durée restante. SEM impose aussi une heure avant laquelle le réseau n'est pas
autorisé, tout en autorisant le solaire. Cette restriction explicite doit rester
en amont de la demande de courant. Copier le mode rapide EVCC sans cette couche
modifierait le comportement demandé.

## Comparaison avec SEM 0.1.14

| Sujet | EVCC étudié | SEM actuel / effet |
| --- | --- | --- |
| Grandeur centrale | Courant en A | Puissance en W, puis conversion entière en A |
| Limite de circuit | Courant réel + marge mesurée | En mesures dites incohérentes, retrait du dépassement à la consigne précédente |
| Répétition d'une mesure | Calcul stable depuis le réel | Même dépassement retranché à chaque cycle de 2 s |
| Cohérence des sources | Acquisition, réception locale et tolérance de stabilisation | Fenêtre de 2 s entre HA et OCPP ; ordre strict de dates pour la confirmation |
| Source puissance borne | Compteur dédié ou compteur intégré sélectionné | La puissance HA remplace systématiquement celle OCPP si elle existe |
| Confirmation | Courant offert, autorisation et état physique séparés | Toute commande non observée bloque globalement les augmentations |
| Suspension OCPP | Profil à 0 A | Fin de transaction distante |
| Profil Wallbox courant | Relatif, variante explicite FW5 | Absolu, pile 0 fixe, changement de type selon transaction |
| Démarrage lent | Stabilisation et synchronisation | Attente initiale de 5 min ajoutée, mais autres blocages encore présents |
| Reboot | Redécouverte et synchronisation de l'état | Commandes acceptées restaurées comme inconnues ; connexion/auth à mieux diagnostiquer |

Fichiers SEM concernés : `backend/app/engine/engine.py`, `phase_limits.py`,
`budget.py`, `runtime/coordinator.py`, `runtime/dispatcher.py` et
`connectors/ocpp/{profiles,registry,station,metering,server}.py`.

## Rejeu numérique de l'arrêt observé le 28 octobre

Dans les observations de production déjà relevées en lecture seule : L1 monte à
22,376 A, la borne mesure 20,3 A, la limite est 20 A avec 1 A de marge, et la
dernière consigne est 17 A. La mesure réseau ne change pas entre trois décisions.

Avec la logique EVCC adaptée à la phase utilisée :

```
limite effective = 20 - 1 = 19 A
consigne admissible = 20,3 + 19 - 22,376 = 16,924 A
```

Le connecteur OCPP EVCC peut transmettre 16,9 A ; une borne limitée aux ampères
entiers recevrait 16 A. Refaire le calcul avec les mêmes mesures conserve cette
valeur. SEM est passé de 17 à 13 puis 9 A avant de suspendre, parce qu'il repartait
de la consigne précédente sans nouvelle mesure. Ce cas doit devenir un test de
régression reproduisant les dates et plusieurs cycles.

L'autre anomalie, 20,3 A mesurés pour 17 A demandés, ne peut pas être attribuée
avec certitude à une cause unique par lecture du code : profil non prioritaire,
expiration, comportement firmware ou décalage de mesure restent des hypothèses.
Elle exige une trace du profil accepté, du courant offert et du courant réel,
puis une validation matérielle après déploiement autorisé.

## Code et tests à reprendre, pas seulement une formule

| Sources EVCC | Partie à adapter / comparer |
| --- | --- |
| `core/circuit/circuit.go` et `circuit_test.go` | Validations courant/puissance, marges et circuits parents |
| `core/loadpoint.go` : `effectiveCurrent`, `pvMaxCurrent`, `setLimit`, `syncCharger` | Régulateur, temporisations, application et synchronisation |
| `core/loadpoint_circuit_test.go` | Maintien de 6 A sans surcharge réelle |
| `core/loadpoint_phases.go` | Nombre de phases effectives ; pas de commutation non supportée |
| `charger/ocpp.go` | Consigne en A, activation/suspension par profil, types de profils |
| `charger/ocpp/connector*.go`, tests associés | Fraîcheur locale, ordre des mesures, transaction, reconnexion |
| Templates Wallbox courant et FW5 | Compatibilité dépendant du firmware |
| `core/soc/estimator.go`, `core/wrapper/chargerater.go` | Comparaison avec le suivi SoC/énergie existant à préserver |

Les tests d'adaptation devront couvrir également : L2 surchargée alors que la
voiture est sur L1 ; recharge triphasée et phase limitante ; injection signée ;
montée progressive après baisse des autres usages ; refus/absence de réponse de
la borne ; première mesure retardée ; capteur HA inchangé mais relu avec succès ;
arrêt immédiat à la fin d'autorisation réseau ; objectif SoC ; reprise après
redémarrage avec identifiants persistants et sans rejouer une ancienne commande.

## Décision d'intégration encore à prendre

Le noyau EVCC Go est lié à ses registres de configuration, son site, ses bus
d'événements, ses métriques et ses interfaces de matériels. Le déplacer tel quel
dans le backend Python n'est pas un simple import de bibliothèque.

Deux voies réalistes ont été présentées : un port du noyau et des tests dans
l'application existante, ou un service EVCC supplémentaire derrière l'interface.
Le port est recommandé pour respecter le choix antérieur d'une application
indépendante. Il devra documenter les écarts nécessaires : correspondance des
phases physiques, autorisations de planning, suivi Peugeot persistant et politique
de fonctionnement hors ligne. La conception précisera les comportements communs
dont l'équivalence sera effectivement vérifiée ; elle ne revendiquera pas une
équivalence de toutes les fonctionnalités EVCC non intégrées.

La correction des identifiants OCPP après reboot fait partie de la reprise de
connexion à concevoir. Le stockage local a déjà conservé un secret fictif entre
deux créations d'application ; le symptôme utilisateur ne prouve donc pas encore
une perte du secret. Le diagnostic doit distinguer secret absent, refus
d'authentification, connexion concurrente et reconnexion de la borne, sans
afficher de mot de passe.
