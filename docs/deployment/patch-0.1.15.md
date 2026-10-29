# 0.1.15 — régulation de recharge adaptée d’EVCC

Cette version remplace la régulation de la voiture, les profils OCPP et
l’estimation de batterie par des adaptations du code EVCC. L’application Python,
son interface et son contrôleur de ballon sont conservés. Source figée :
`evcc-io/evcc@9404d825d6a659d8ce7f47d3b0d2e14ac04506e0` ; provenance et licence
MIT dans `docs/third-party/evcc-MIT.txt`. Les fonctions EVCC non intégrées
(commutation automatique des phases, circuits parents arbitraires, autres
protocoles de borne) ne sont pas annoncées comme prises en charge.

## Recharge et limites électriques

- Le courant réellement mesuré et la marge restante sur les phases configurées
  déterminent la consigne, avec résolution de 0,1 A. Une surcharge réduit la
  consigne ; si le courant disponible passe sous le minimum, la charge est suspendue.
- Une même mesure décalée ne soustrait plus plusieurs fois le dépassement à la
  consigne précédente. Les augmentations ordinaires attendent 30 secondes ;
  les réductions pour surcharge et les arrêts explicites restent immédiats.
- Le mode solaire reprend les temporisations EVCC et démarre au courant minimal.
  La fin d’une plage réseau, Pause, un défaut et l’objectif de batterie restent
  prioritaires sur la temporisation des nuages.
- Les mesures OCPP utilisables passent avant la puissance HA de la voiture.
  Les sources réseau/borne peuvent être reçues à des instants différents sans
  produire artificiellement une absence de confirmation.
- La première mesure conserve une tolérance de cinq minutes. Cette tolérance
  ne retarde jamais la correction d’une surcharge effectivement mesurée.

## Profils Wallbox et reconnexion

Le réglage « Compatibilité OCPP » propose Automatique, Wallbox, Wallbox firmware 5
et Standard. En automatique, le modèle/firmware du BootNotification sélectionne
le profil. Wallbox utilise un profil relatif ; le firmware 5 utilise un profil
absolu et le niveau de pile 0, comme le modèle EVCC correspondant.

La pause normale envoie un profil à 0 A sans fermer la transaction. Si cette
suspension est refusée ou reste ignorée après le délai de stabilisation,
une demande d’arrêt de transaction sert de repli. Le profil EVCC remplace
l’ancien profil appartenant à SEM ; aucun effacement général des profils
installés dans la borne n’est effectué.

Les limites sont maintenant des profils persistants `TxDefaultProfile`.
**Si SEM est arrêté, la dernière limite reste installée dans la borne, mais les
plannings et la régulation dynamique ne sont plus exécutés.** Un profil positif
peut donc continuer à autoriser la charge jusqu’au retour du contrôleur. Ce choix
reprend le fonctionnement EVCC et évite l’expiration d’un profil qui laisserait
revenir la borne à sa puissance matérielle maximale.

Les accès restent chiffrés dans le volume `/data`. Les réglages affichent si
l’accès OCPP est enregistré, la connexion, le firmware et un motif d’échec
sans révéler le secret. Enregistrer un champ de mot de passe vide conserve le
secret existant. La reconnexion avec une nouvelle instance d’application et le
même répertoire de données est testée ; une perte de secret n’a pas été reproduite.

## Batterie Peugeot

La date Peugeot n’intervient plus dans le calcul ni dans l’autorisation du SoC.
La première valeur valide amorce l’estimateur ; une valeur identique laisse
progresser l’estimation selon les kWh de la borne. Une valeur différente recale
immédiatement l’estimation sur cette valeur, même plus basse. Une erreur d’API
laisse continuer une estimation déjà amorcée.

L’estimateur commence avec le rendement EVCC de 85 % puis apprend le gradient
énergie/pourcentage. La capacité utile du véhicule doit être renseignée pour
cette estimation. L’ancien champ de rendement fixe reste lisible dans les
configurations existantes mais ne commande plus le calcul. La même estimation
sert à l’affichage et à l’arrêt à l’objectif.

L’état de l’estimateur, les sessions, les kWh et les coûts sont persistés.
Une ancienne référence dont l’index d’énergie est connu conserve cette base ;
sinon la migration repart du dernier pourcentage connu et de l’index courant.
Les contrôles d’intégrité des compteurs restent applicables : une rupture réelle
de compteur ne devient pas une autorisation illimitée de charger.

## Mise à jour Portainer

Attendre la réussite du workflow de publication du tag `v0.1.15`, puis utiliser :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.15
```

Ou définir `SEM_VERSION=0.1.15` avec le Compose du dépôt. Conserver le port,
les paramètres et le volume `/data` existants. Avant mise à jour, effectuer
une sauvegarde cohérente de ce volume selon `backup-restore.md`, incluant la
base SQLite et la clé de chiffrement ; cette clé est nécessaire aux secrets.

Le développement et les tests utilisent des bornes simulées et des données
jetables. Aucune commande de recharge, modification HA ou installation sur le
serveur réel n’est effectuée par ces tests. Après déploiement autorisé, vérifier
sur la Wallbox la connexion, la limite appliquée, une réduction sous charge,
une pause/reprise et un redémarrage du serveur. Les essais matériels restent
nécessaires avant de déclarer le fonctionnement validé sur cette installation.
