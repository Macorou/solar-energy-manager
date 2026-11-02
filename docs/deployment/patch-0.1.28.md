# Mise à jour 0.1.28 — Publication vers Home Assistant par MQTT

SEM publie désormais ses calculs et ses décisions dans Home Assistant, en lecture seule, par MQTT avec la découverte automatique. Le point principal : un **prix instantané de l'énergie en EUR/kWh** pour le site, pour la voiture et pour le ballon. Il peut remplacer l'entité « Costs Loadpoints » d'EVCC dans l'onglet Énergie.

## Configuration

Réglages → Intégrations → Services locaux → carte **MQTT** :
- **Courtier** : `hôte:port`, par exemple `192.168.1.30:1883`.
- **Sujet** : `sem` par défaut. Le laisser vide désactive la publication. `evcc` est refusé, pour ne pas écraser les sujets d'EVCC.
- **Identifiant client**, **nom d'utilisateur**, **mot de passe** : facultatifs. Le mot de passe est chiffré et n'est jamais réaffiché ni écrit dans le journal.
- **Certificats auto-signés**, et dans les paramètres avancés **TLS** et **préfixe de découverte** (`homeassistant`).

Le bouton **Tester** vérifie la connexion. Le bouton **Supprimer** retire les entités de Home Assistant. Si le courtier est injoignable, la carte prévient qu'elles sont à supprimer à la main.

La carte affiche Connecté, Hors connexion ou Désactivé, ainsi que l'heure du dernier envoi.

## Entités publiées

Elles sont regroupées en trois appareils.
- **SEM – Installation** : prix de l'énergie du site, surplus solaire disponible, heures creuses, pilotage actif, problème en cours.
- **SEM – <borne>** :
  - prix de l'énergie de la voiture ;
  - batterie (estimée ou relevée), autonomie, voiture branchée ;
  - puissance, état, raison, mode ;
  - objectif et objectif sur surplus ;
  - énergie, coût et part solaire de la session (avec un attribut « partiel ») ;
  - avertissement du programme.
- **SEM – <ballon>** : prix de l'énergie du ballon, température, consigne en cours et sa source, puissance, état, raison, mode.

Les puissances et les prix sont envoyés au plus toutes les 10 s, les autres valeurs dès qu'elles changent. Une valeur manquante rend l'entité « indisponible », jamais 0 €/kWh. Le VIN, les comptes et les secrets ne sont jamais publiés.

## Calcul des prix

- **Site** : mélange réseau/solaire de toute la consommation, soit le prix effectif déjà affiché par SEM.
- **Voiture** : servie en dernier par le solaire. L'import réseau lui est compté en premier.
- **Ballon** : servi par le solaire après la maison et avant la voiture.
- **Appareil à l'arrêt** : le prix qu'aurait son premier kWh.

Le coût et la part solaire des **sessions de charge** affichés dans SEM suivent désormais la règle de la voiture. Les sessions déjà terminées gardent leurs valeurs.

Dans l'onglet Énergie de Home Assistant, choisir l'entité « Prix de l'énergie de la voiture » avec l'option « Utiliser une entité avec le prix actuel ». L'énergie reste celle de la Wallbox.

## Fonctionnement

MQTT est indépendant du pilotage. Un courtier injoignable, lent ou qui refuse l'authentification ne retarde ni la charge, ni la chauffe, ni l'arrêt de SEM. Seuls la carte et le journal le signalent, et SEM se reconnecte tout seul. Quand Home Assistant redémarre, les entités sont annoncées à nouveau.

## Portainer

**Sauvegarder le volume /data avant la mise à jour.** Dès que 0.1.28 enregistre les réglages, ils contiennent la section `mqtt`, que 0.1.27 refuse. Un retour en arrière se fait donc avec la sauvegarde, pas avec le volume mis à jour.

Utiliser SEM_VERSION=0.1.28 ou ghcr.io/macorou/solar-energy-manager:0.1.28, télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3.

Après la mise à jour :
1. Configurer la carte MQTT, puis cliquer sur Tester.
2. Vérifier que les appareils « SEM – … » apparaissent dans Home Assistant (Paramètres → Appareils et services → MQTT).
3. Choisir le prix de la voiture dans l'onglet Énergie.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage, un courtier MQTT et des transports de test ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
