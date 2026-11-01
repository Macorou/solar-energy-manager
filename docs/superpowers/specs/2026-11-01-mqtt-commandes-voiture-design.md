# Commandes de la voiture depuis Home Assistant (MQTT)

## Intention

Depuis la 0.1.28, SEM publie son état dans Home Assistant par MQTT, en lecture seule. L'utilisateur veut maintenant piloter la voiture depuis HA sans ouvrir SEM :
- changer le **mode** de la voiture entre trois choix simples ;
- modifier au jour le jour **l'objectif de ses programmes de charge**. Par exemple, 80 % d'habitude et 100 % la veille d'un long trajet.

Ces commandes complètent l'intégration MQTT existante. Voir [la conception MQTT](2026-11-01-mqtt-home-assistant-design.md) : courtier, découverte automatique, appareils « SEM – … ».

Le travail comprend aussi un changement de comportement demandé en même temps. Le mode **Manuel** de la voiture ne se retirait jamais tout seul. Désormais, il **repasse en Auto quand on débranche la voiture**.

## Objectifs

1. **Liste « Mode de la voiture »** (`select` dans HA) sur chaque appareil borne « SEM – <borne> ». Elle propose trois choix :
   - **Auto** → mode SEM `planned` (Planifié). C'est toujours Planifié, sans mémoriser le mode automatique précédent ;
   - **Manuel** → mode `manual` ;
   - **Pause** → mode `off`.

   La liste affiche le mode actuel et suit les changements faits dans SEM.
2. **Un réglage « Objectif – <nom du programme> »** (`number` dans HA, de 1 à 100 %, par pas de 1) pour chaque programme de charge dont le véhicule est celui de la borne. Les programmes inactifs sont inclus. Une valeur envoyée depuis HA modifie `target_soc` de ce programme, exactement comme une modification faite dans Planning.
3. **Retour automatique du mode Manuel en Auto au débranchement**. Quand une borne en mode `manual` voit la voiture passer de branchée à débranchée, SEM la remet en `planned`. Cela vaut quel que soit l'endroit d'où le mode Manuel a été choisi : SEM ou HA.
4. **Une case « Autoriser les commandes depuis Home Assistant »** dans la carte MQTT, décochée par défaut.
   - Décochée : SEM ne crée pas la liste ni les réglages dans HA (ils sont retirés s'ils existaient) et ignore tout message de commande.
   - Cochée : la carte affiche un avertissement : « Toute personne ou tout appareil ayant accès à votre courtier MQTT pourra changer le mode de charge de la voiture. »

## Hors périmètre

- Les commandes du ballon.
- Activer ou désactiver un programme, en créer, en supprimer ou en renommer depuis HA. Les programmes restent gérés dans Planning.
- Régler depuis HA l'objectif habituel ou l'objectif sur surplus solaire.
- Les modes Solaire et Heures creuses + solaire dans la liste HA.
- « Charger maintenant », la puissance du mode Manuel, les courants.
- Toute modification de l'interface Planning.

## À ne jamais faire

- **Une commande ne doit jamais contourner les garde-fous existants.** Les commandes HA appliquent exactement les mêmes règles que les boutons de SEM (fichier `backend/app/api/devices.py`) :
  - **Manuel** est refusé si l'appareil n'est pas activé (`armed`) ;
  - **Auto** est refusé si l'appareil n'est pas activé, ou si une commande précédente a un résultat inconnu à acquitter (règle de `resume`) ;
  - **Pause** est toujours accepté, comme le bouton Pause.

  La logique doit être partagée avec les routes web, pas recopiée.
- **Une panne MQTT ou un message invalide ne doit jamais perturber le pilotage.** C'est déjà le cas pour la publication et cela reste vrai. Une commande mal formée est ignorée et écrite une fois dans le journal, sans exception dans la boucle.
- **Ne jamais rejouer une commande ancienne.** Un message de commande reçu avec l'indicateur « retained » est ignoré. Sinon, une commande restée sur le courtier serait réappliquée à chaque reconnexion.
- **Ne jamais publier ni journaliser de secret.** Les règles de la conception MQTT s'appliquent toujours.
- **Le retour en Auto au débranchement ne doit jamais se déclencher sur une information douteuse.** Il faut une transition observée de « voiture branchée » à « voiture débranchée » pendant que la borne est connectée. Une borne hors connexion, ou un état de branchement inconnu, ne compte pas.

## Comportement attendu

### Liste « Mode de la voiture »

| Mode SEM | Affiché dans HA |
|---|---|
| `planned` | Auto |
| `manual` | Manuel |
| `off` | Pause |
| `solar`, `off_peak_solar` | état inconnu (la liste reste utilisable) |

- **Choisir Auto** fait passer en `planned`, et en sort quel que soit le mode précédent. Comme pour `resume`, cela vide l'entrée `manual_controls` de l'appareil et appelle `engine.forget`.
- **Choisir Manuel** suit la même procédure que la route `POST /devices/{id}/manual`.
- **Choisir Pause** suit la même procédure que `POST /devices/{id}/pause`.
- **Commande refusée** : le journal reçoit un avertissement, par exemple « Commande Home Assistant refusée : Manuel – activer et vérifier cet appareil ». SEM republie aussitôt l'état réel, et la liste de HA revient sur le mode en vigueur.
- **Commande acceptée** : le journal reçoit une ligne INFO, par exemple « Mode Pause demandé depuis Home Assistant ». Si un événement d'appareil est enregistré, son origine est `'home_assistant'`, comme `'web'` aujourd'hui. Le nouvel état est publié tout de suite, sans attendre l'intervalle de 10 s.

### Réglages « Objectif – <programme> »

- **Valeur affichée** : le `target_soc` actuel du programme.
- **Valeur acceptée** : un nombre de 1 à 100. Toute autre valeur est ignorée et journalisée.
- **Enregistrement** : il passe par la même validation que l'API des programmes (`persist` dans `backend/app/api/schedules.py`, c'est-à-dire `SettingsDocument`).
- **Journal** : une ligne INFO, par exemple « Objectif du programme « Semaine » réglé à 100 % depuis Home Assistant ».
- **Programme créé, renommé ou supprimé dans SEM** : le réglage correspondant apparaît, change de nom ou disparaît de HA. Le mécanisme d'annonce actuel le permet déjà, puisqu'il retire les entités qui ne sont plus annoncées.
- **Programme supprimé pendant qu'une commande arrive** : la commande est ignorée et journalisée.

### Retour en Auto au débranchement

- **Déclencheur** : une borne en mode `manual`, connectée (`state.connected`), dont `vehicle_connected` passe de `True` à `False`.
- **Effet** : le mode passe à `planned`, l'entrée `manual_controls` est retirée, les réglages sont enregistrés et `engine.forget` est appelé. Le journal reçoit la ligne INFO « Voiture débranchée : fin du mode Manuel, retour en Auto (Planifié) ».
- **Interface web** : la mention « le mode manuel reste actif jusqu'à une intervention utilisateur » est remplacée par « jusqu'au débranchement de la voiture ». Cela concerne la description `ManualRequest.duration_minutes` et les textes de l'interface qui le disent.

### Carte MQTT

- **Nouveau champ** `commands_enabled: bool = False` dans `MqttConfig`. Les réglages enregistrés par une version antérieure le reçoivent par défaut à la lecture (comportement de la 0.1.29).
- **Case à cocher** « Autoriser les commandes depuis Home Assistant », avec l'avertissement ci-dessus quand elle est cochée.

### Précisions techniques (choix de Claude après relecture)

- **Transition débranchée**
  - Le dernier état « branchée » connu est conservé quand l'état devient inconnu (`None`, borne en défaut, par exemple). `True` → `None` → `False` compte donc comme un débranchement.
  - Le dernier état connu est oublié quand la borne passe hors connexion (`connected=False`). Un débranchement pendant une coupure n'est pas détecté et la voiture reste en Manuel, ce qui est le choix prudent.
  - Le premier état observé après un redémarrage de SEM ne déclenche rien.
  - Tests attendus : `True`→`False`, `True`→`None`→`False`, `True`→hors connexion→`False`, premier état après redémarrage.
- **Verrou** : les commandes MQTT prennent `coordinator.lock`, comme la boucle. Ainsi, `tick()` ou `policies()` ne réenregistrent pas une copie périmée des réglages par-dessus une commande.
- **Accès au coordinateur** : le service MQTT reçoit le coordinateur, ou les fonctions partagées. Aujourd'hui, il ne reçoit qu'un fournisseur d'état.
- **Indicateur « retained »** : l'enveloppe aiomqtt et le client factice des tests exposent cet indicateur, pour pouvoir ignorer les commandes retenues.
- **Commande refusée** : la republication de l'état réel contourne la vérification « valeur inchangée » du publieur.
- **`paused_modes`** : ni Auto depuis HA ni le retour au débranchement n'y touchent.
- **Bornes sans véhicule** (`vehicle_id` vide) : elles n'ont aucun réglage d'objectif.

## Choix techniques laissés au constructeur

- Les noms de sujets, en suivant la convention existante. Par exemple `<sujet>/<borne>/car_mode/set` et `<sujet>/<borne>/program_<id>_target/set`, avec un abonnement générique `<sujet>/+/+/set`.
- La façon de représenter l'état inconnu de la liste. Il faut que HA affiche « inconnu » sans rendre la liste indisponible ; le publieur actuel remplace un texte vide par « Aucun », ce qui ne convient pas ici.
- L'endroit où partager la logique des modes entre les routes web et MQTT (module de service, fonctions du coordinateur…), tant que les routes web gardent exactement leur comportement.
- La façon de détecter la transition branchée → débranchée : mémoire de l'état précédent par borne dans le coordinateur ou le suivi des sessions.
- Les tests, avec un client MQTT factice et des données fictives, comme pour la 0.1.28.

## Décisions de l'utilisateur

- Auto signifie toujours Planifié.
- Les programmes multiples restent comme aujourd'hui : tous les programmes actifs s'appliquent selon leurs jours. Pas de « programme choisi ».
- HA ne règle que l'objectif des programmes de charge.
- Le mode Manuel repasse en Auto au débranchement.

## Choix de Claude, validés par l'utilisateur

- Les commandes sont désactivées par défaut, derrière une case à cocher.
- Chaque commande est journalisée.
- Les modes Solaire et Heures creuses + solaire s'affichent comme un état inconnu dans la liste HA.
