# Mise à jour 0.1.31 — Piloter la voiture depuis Home Assistant

## Nouveautés

### Commandes depuis Home Assistant (MQTT)

Home Assistant peut maintenant piloter la voiture, à condition de l'autoriser. Dans Réglages → Intégrations → Services locaux → **MQTT**, cocher **« Autoriser les commandes depuis Home Assistant »**. La case est décochée par défaut. Une fois cochée, la carte rappelle que toute personne ou tout appareil ayant accès au courtier MQTT pourra changer le mode de charge de la voiture.

Deux types d'entités apparaissent alors sur l'appareil « SEM – <borne> » :
- **Mode de la voiture** (liste) :
  - **Auto** passe en mode Planifié ;
  - **Manuel** passe en mode Manuel ;
  - **Pause** met la voiture en pause.

  Les modes Solaire et Heures creuses + solaire s'affichent comme « inconnu ».
- **Objectif – <programme>** (de 1 à 100 %) : un réglage par programme de charge de la voiture, qui modifie l'objectif de ce programme comme dans Planning.

**Règles appliquées :**
- Les commandes respectent les mêmes garde-fous que les boutons de SEM : Manuel et Auto sont refusés si la borne n'est pas activée.
- Demander le mode déjà actif ne renvoie aucune commande à la borne.
- Une commande restée sur le courtier (« retained ») est ignorée.
- Chaque commande, acceptée ou refusée, est écrite dans le journal, et l'état réel est republié aussitôt.
- Décocher la case retire ces entités de Home Assistant.

### Fin du mode Manuel au débranchement

Le mode Manuel de la voiture ne restait jamais actif « pour toujours » par choix, mais par absence de règle. Désormais, **il repasse en Auto (Planifié) quand on débranche la voiture**, qu'il ait été choisi dans SEM ou dans Home Assistant.

SEM ne prend que des informations sûres : seul un état envoyé par la borne après sa dernière connexion ou son dernier redémarrage compte. Si la borne est hors connexion au moment du débranchement, ou si elle ne renvoie pas son état après une coupure, la voiture reste en Manuel ; il faut alors la remettre en Auto soi-même.

## Portainer

**Sauvegarder le volume /data avant la mise à jour.** Dès que la 0.1.31 enregistre les réglages, ils contiennent le champ `commands_enabled` de la section MQTT, que les versions précédentes refusent. Un retour en arrière se fait donc avec la sauvegarde, pas avec le volume mis à jour.

Utiliser ensuite SEM_VERSION=0.1.31 ou ghcr.io/macorou/solar-energy-manager:0.1.31. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite reste en version 3.

**Retour en arrière :** restaurer la sauvegarde faite avant la 0.1.31. Si les commandes avaient été activées, supprimer aussi à la main, dans Home Assistant, les entités « Mode de la voiture » et « Objectif – … » restées en place.

Aucune commande matérielle n'a été envoyée pendant le développement. Les essais utilisent un stockage, un courtier MQTT et des transports de test ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests.
