# 0.1.16 — confirmation d’arrêt avec voiture débranchée

Symptôme signalé après reboot : la carte indique « Débranchée », 0 W, mais
conserve « Arrêt en cours » et une demande à 0 W acceptée. Le serveur a été
identifié en 0.1.15 par son endpoint public de santé. L’accès privé à son état
détaillé demande une reconnexion ; le motif initial « Suspension refusée »
n’a donc pas été diagnostiqué sur les journaux de cette installation.

La cause du blocage de confirmation a été reproduite dans le code : le statut
OCPP `Available` et la fin de transaction créaient une puissance estimée à zéro
sans date de vérification. La confirmation d’arrêt exigeait cette date.
Le reboot conservait correctement l’ancienne commande non résolue, qui restait
alors en attente malgré le nouveau statut de borne.

Le correctif :

- Date localement la réception des statuts natifs et la vérification du zéro
  associé, sans confondre cette réception avec l’horodatage fourni par la borne.
- Confirme une demande d’arrêt à partir d’un statut natif frais reçu après la
  demande, d’une puissance zéro vérifiée, de l’absence de défaut et de départ
  en attente. Hors suspension EVSE, l’absence de transaction reste exigée.
- Cette preuve d’arrêt ne dépend plus du capteur de puissance du logement.
- Relit le statut toutes les 15 secondes pendant une confirmation manquante.
  Ces lectures ne commandent ni charge ni arrêt supplémentaires.
- Conserve un seul préfixe « Arrêt en cours » ou « Vérification requise », avec
  le motif d’origine, au lieu de les réempiler lors des reprises.

Les états hors connexion, anciens, en charge, non nuls, en défaut ou avec une
transaction/demande de départ incompatible ne deviennent pas des confirmations
valables. Aucun effacement général des commandes ou défauts persistants n’est
effectué.

Les tests reproduisent le reboot avec une commande d’arrêt inconnue, puis un
statut débranché frais (avec horodatage fournisseur récent ou ancien), les
contre-exemples précédents et la relecture périodique. Aucune commande n’a été
envoyée à l’installation pendant le diagnostic ou les tests.

Après réussite du workflow de publication, utiliser dans Portainer :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.16
```

Ou définir `SEM_VERSION=0.1.16`. Conserver le volume `/data`, les ports et les
réglages existants, et sauvegarder le volume avant mise à jour. La première
nouvelle confirmation native de la borne permet de résoudre l’ancien arrêt.
