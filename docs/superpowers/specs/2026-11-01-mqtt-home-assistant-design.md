# Intégration MQTT vers Home Assistant

## Intention

L'utilisateur veut retrouver dans Home Assistant les calculs et les décisions de SEM, et surtout un **prix instantané de l'énergie** par appareil. Il le renseignera dans l'onglet Énergie de Home Assistant, avec l'option « Utiliser une entité avec le prix actuel ». Aujourd'hui, ce prix vient de l'entité « Costs Loadpoints [Site] » publiée par EVCC. SEM doit fournir l'équivalent pour le site, puis un prix propre à la voiture et un prix propre au ballon.

Le transport choisi est **MQTT, avec la découverte automatique de Home Assistant**. Un courtier Mosquitto existe déjà sur le réseau local, avec un compte dédié. Les entités doivent apparaître seules dans Home Assistant, regroupées par appareil, et pouvoir y être renommées.

## Objectifs

- Un module **« MQTT »** dans Réglages → Intégrations → **Services locaux**, à côté de « Serveur OCPP » et de « Gestion de la charge ».
- La publication des entités décrites plus bas, en **lecture seule**.
- **Trois prix en EUR/kWh** (site, voiture, ballon), utilisables directement dans l'onglet Énergie.
- Le coût et la part solaire des sessions de charge calculés par SEM suivent désormais **la même règle que le prix de la voiture**.

## Hors périmètre

- Les **commandes depuis Home Assistant** : mode, objectifs, « Charger maintenant ». Elles viendront dans une version ultérieure.
- La republication des mesures que Home Assistant possède déjà :
  - réseau, solaire, maison et phases ;
  - **énergie de la Wallbox**, que l'utilisateur prend déjà dans l'intégration Wallbox de Home Assistant.
- Le recalcul des sessions de charge déjà terminées.

## À ne jamais faire (anti-objectifs)

- **Une panne MQTT ne doit jamais perturber le pilotage.** Courtier injoignable, refus d'authentification, lenteur : SEM continue de charger la voiture et de chauffer le ballon exactement pareil. MQTT ne doit ni bloquer ni ralentir la boucle de 2 s, ni lever d'exception qui la casse. Seul le journal en garde trace.
- **Ne jamais publier de faux 0 €/kWh.** Si une donnée nécessaire manque, l'entité passe en « indisponible » : Home Assistant ignore alors ce moment dans le calcul du coût.
- **Ne jamais publier ni journaliser de secret ni de donnée personnelle** : mot de passe MQTT, jetons, VIN, adresse e-mail.
- Ne pas réutiliser les sujets `evcc` : EVCC peut encore tourner à côté.

## Contraintes

- Python 3.12, FastAPI, boucle asyncio existante (`Coordinator`), React 19 et Vite côté interface. Les dépendances sont épinglées dans `backend/pyproject.toml`.
- Le conteneur a un système de fichiers en lecture seule, hors `/data` et `/tmp`.
- Les réglages passent par `SettingsDocument`, qui refuse tout champ inconnu (`extra='forbid'`). Ajouter une section `mqtt` rend donc le volume illisible par les versions antérieures, dès que les réglages ont été enregistrés. La note de version devra demander une sauvegarde du volume avant la mise à jour, comme pour la 0.1.25.
- Les secrets passent par `SecretStore`, chiffré avec `secrets/master.key`. Le champ secret reste vide dans l'interface après enregistrement, comme pour Home Assistant, Peugeot et Ariston.
- Tests uniquement sur des données fictives et un dossier `SEM_DATA_DIR` jetable. Aucun test contre l'installation réelle, aucun courtier réel dans la suite de tests.

## Le module de connexion (décidé)

Les champs sont calqués sur le formulaire MQTT d'EVCC que l'utilisateur utilise déjà.

| Champ | Détail |
|---|---|
| Courtier | `hôte:port`, par exemple `192.168.1.30:1883` |
| Sujet (facultatif) | Préfixe des sujets. **`sem` par défaut. Vide = publication désactivée** |
| Identifiant client (facultatif) | Vide = `sem-` suivi d'un suffixe aléatoire, stable tant que SEM tourne |
| Nom d'utilisateur (facultatif) | |
| Mot de passe (facultatif) | Secret chiffré, champ vide après enregistrement |
| Autoriser les certificats auto-signés | Case à cocher |
| Paramètres avancés (repliés) | Connexion chiffrée (TLS) ; préfixe de découverte Home Assistant, `homeassistant` par défaut |

Le formulaire propose **Annuler**, **Supprimer** (efface la configuration et le mot de passe) et **Enregistrer**. Un bouton de test de connexion, comme pour Home Assistant, est souhaitable.

La carte affiche un badge **Connecté / Hors connexion / Désactivé** et l'heure du dernier envoi réussi. En cas d'erreur, elle montre une raison courte : courtier injoignable, authentification refusée, etc.

Si MQTT est supprimé ou désactivé, les entités disparaissent proprement de Home Assistant : SEM publie une configuration de découverte vide pour chacune.

## Les entités publiées (décidé)

Il y a un appareil Home Assistant par groupe. **Mon choix** : un appareil « SEM – Installation », puis un appareil par équipement configuré dans SEM, nommé « SEM – » suivi du nom de l'équipement. Avec l'installation actuelle, ça donne une voiture (borne Wallbox) et un ballon.

Les noms d'entités sont en français. Les identifiants uniques sont stables et dérivés de l'identifiant interne de l'équipement dans SEM, jamais du VIN.

**SEM – Installation**

| Entité | Type et unité |
|---|---|
| **Prix de l'énergie du site** | capteur, EUR/kWh, 3 décimales |
| Surplus solaire disponible | capteur, W |
| Heures creuses | binaire |
| Pilotage actif | binaire |
| Problème en cours | capteur texte : premier message d'erreur de SEM, vide sinon |

**SEM – Voiture** (un par borne)

| Entité | Type et unité |
|---|---|
| **Prix de l'énergie de la voiture** | capteur, EUR/kWh, 3 décimales |
| Batterie | capteur, %, avec un attribut qui précise si elle est estimée ou relevée |
| Autonomie | capteur, km |
| Puissance de charge | capteur, W |
| État | capteur texte, même libellé que l'interface SEM |
| Raison | capteur texte, raison affichée par SEM |
| Mode | capteur texte : Automatique / Manuel / Pause |
| Voiture branchée | binaire |
| Objectif | capteur, % |
| Objectif sur surplus solaire | capteur, %, indisponible si non réglé |
| Énergie de la session | capteur, kWh |
| Coût de la session | capteur, € |
| Part solaire de la session | capteur, % |
| Avertissement du programme | capteur texte, vide sinon |

**SEM – Ballon** (un par ballon)

| Entité | Type et unité |
|---|---|
| **Prix de l'énergie du ballon** | capteur, EUR/kWh, 3 décimales |
| Température | capteur, °C |
| Consigne en cours | capteur, °C, avec la source (réseau ou solaire) en attribut |
| Puissance de chauffe | capteur, W |
| État, Raison, Mode | capteurs texte, comme pour la voiture |

**Fréquence** : un envoi dès qu'une valeur change. Les puissances et les prix sont envoyés au plus toutes les 10 s par entité. Une disponibilité globale indique quand SEM est hors ligne : par exemple un message de « dernière volonté » MQTT, ou l'équivalent.

## Le calcul des prix (décidé)

Le tarif réseau est le capteur de prix configuré dans Home Assistant (`snapshot.price`). Le prix du solaire est le réglage existant `solar_price_per_kwh`, à 0 par défaut. L'import réseau est la partie positive de la mesure réseau.

**Prix du site** : c'est le prix effectif existant (`mix_context` dans `backend/app/runtime/charging.py`), soit le mélange réseau/solaire de toute la consommation. C'est l'équivalent de « Costs Loadpoints [Site] » d'EVCC.

**Ordre d'attribution du solaire**, choisi par l'utilisateur : le solaire couvre d'abord **la maison**, puis **le ballon**, et **la voiture en dernier**. Inversement, l'import réseau est compté d'abord pour la voiture, puis pour le ballon, puis pour la maison.

- **Voiture** :
  - part réseau = min(puissance voiture, import) ;
  - prix = (part réseau × tarif + (puissance voiture − part réseau) × prix solaire) ÷ puissance voiture.
- **Ballon** :
  - part réseau = min(puissance ballon, max(0, import − puissance voiture)) ;
  - prix sur le même modèle.
- **Exemple de référence**, à mettre en test : solaire 4 kW, maison 0,5 kW, ballon 2,5 kW, voiture 3 kW, import 2 kW, tarif 0,165 €, prix solaire 0. On obtient voiture **0,110**, ballon **0,000**, site **0,055 €/kWh**.
- **Appareil à l'arrêt** (≤ 20 W) : on publie le prix qu'aurait son premier kWh selon le même ordre.
  - Voiture : le tarif si le site importe, sinon le prix solaire.
  - Ballon : le tarif si l'import dépasse la puissance de la voiture, sinon le prix solaire.
- **Donnée manquante ou périmée** (tarif, réseau, puissance de l'appareil), selon la règle d'âge habituelle de SEM : l'entité passe en **indisponible**. Exception : le tarif n'est pas nécessaire si toute l'énergie de l'appareil est solaire.

**Sessions de charge** : le coût et la part solaire des sessions, aujourd'hui calculés avec le mélange du site, utilisent désormais la part réseau de la voiture définie ci-dessus. Le prix publié et le coût affiché dans SEM racontent ainsi la même chose. Les sessions déjà terminées gardent leurs valeurs enregistrées. Le changement s'applique aux énergies attribuées après la mise à jour, y compris dans une session en cours.

## Précisions (choix de Claude, non discutés avec l'utilisateur)

1. **Sessions de charge.** Chaque contexte enregistré par la session garde la part réseau **de la voiture**, calculée à ce moment-là avec la puissance de la voiture et l'import. Le format du contexte et `allocate` sont adaptés en conséquence.
   - Si la voiture lit ≤ 20 W ou n'a pas de puissance utilisable pendant qu'un delta de compteur arrive (décalage de mesure), la règle du premier kWh s'applique : tarif si le site importe, sinon prix solaire.
   - L'énergie solaire est le complément de cette même part (`solar_wh = énergie × (1 − part réseau)`).
   - Sans import réseau lisible, la part reste inconnue (`None`), comme aujourd'hui.
   - Les contextes déjà enregistrés par une session en cours au moment de la mise à jour ne durent que quelques dizaines de secondes : le mélange de sens sur le premier delta est accepté.
2. **Puissance manquante d'un autre appareil.**
   - Dans le calcul du ballon, la puissance de la voiture compte pour 0 si la voiture n'est pas branchée, ou si la borne n'est pas en état « Charging ». Sinon, si sa puissance manque, le prix du ballon est indisponible.
   - De même, la puissance du ballon compte pour 0 s'il est à l'arrêt selon son état natif.
   - La puissance **de l'appareil lui-même** est celle que SEM utilise déjà (`observed_power`). Si elle manque alors qu'il fonctionne, son prix est indisponible.
   - Le prix du site garde sa règle actuelle (`mix_context`).
3. **Plusieurs voitures ou ballons.** L'installation actuelle en a un de chaque, mais les formules se généralisent :
   - les voitures prennent l'import réseau en premier, entre elles par **priorité SEM inverse** (la moins prioritaire d'abord) ;
   - puis viennent les ballons, selon la même règle ;
   - « puissance voiture » dans la formule du ballon = la somme des voitures.
4. **États publiés.**
   - « Pilotage actif » = la boucle de SEM tourne et son dernier passage date de moins de 30 s.
   - Mode : `solar`, `planned` et `off_peak_solar` → **Automatique** ; `manual` → **Manuel** ; `off` → **Pause** ; équipement non activé → **Observation**. Ce sont les libellés de l'interface.
   - L'**objectif** et la **consigne** publiés sont les valeurs effectives affichées sur les cartes de SEM, pas les réglages par défaut :
     - voiture : objectif de l'autorisation en cours, sinon objectif habituel ;
     - ballon : `effective_targets` et `target_sources`.
5. **Problème en cours.** Il reprend la première erreur de `coordinator.errors`. Les codes fournisseurs (`reconnect_required`, `rate_limited`, etc.) sont traduits avec les mêmes libellés français que l'interface. Seuls les codes connus et les messages produits par SEM sont publiés, jamais un texte d'exception brut.
6. **Nettoyage des entités.**
   - À la suppression ou désactivation de MQTT, SEM tente de vider les configurations de découverte.
   - Si le courtier est injoignable, la suppression se fait quand même. La carte et le journal préviennent que les entités restées dans Home Assistant sont à supprimer à la main. Aucun nettoyage différé n'est conservé.
   - Les entités d'un équipement retiré de SEM pendant que MQTT reste actif sont, elles, supprimées automatiquement.
7. `SecretStore` reçoit une méthode de suppression du secret, pour « Supprimer ».

## Laissé au constructeur

- La bibliothèque MQTT. Suggestion : `aiomqtt`, en version stable publiée depuis au moins deux semaines et épinglée.
- La structure des sujets sous le préfixe, le format exact des messages (JSON ou valeur simple), et l'usage des messages retenus (`retain`).
- La découverte par entité ou par appareil, la remise en ligne après un redémarrage de Home Assistant (message `homeassistant/status`), et le délai de reconnexion.
- L'emplacement du code : connecteur, tâche de fond du coordinateur, etc. Contrainte : ne rien faire de bloquant dans la boucle de pilotage.
- Les points d'API (lecture, enregistrement, test, état) et la manière de remonter l'état à la carte.
- Le texte des messages de journal, en français comme le reste.

## Vérification attendue

- Tests unitaires des trois prix : l'exemple de référence, les appareils à l'arrêt, export et import, données manquantes et tarif absent en plein solaire.
- Tests de la session de charge avec la nouvelle règle, sans modifier les sessions terminées.
- Tests de la publication avec un faux client MQTT :
  - contenu des configurations de découverte et identifiants stables ;
  - absence de VIN et de secret ;
  - limitation à 10 s ;
  - indisponibilité ;
  - suppression des entités à la désactivation ;
  - **la boucle de pilotage continue quand le courtier est injoignable ou lent**.
- Tests de l'interface : carte, formulaire et mot de passe non réaffiché.
- Suites complètes backend et frontend, et build.
