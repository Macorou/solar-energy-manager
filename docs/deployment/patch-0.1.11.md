# Mise à jour 0.1.11 — référence Peugeot automatique

## Comportement corrigé

Le dernier pourcentage remonté par Peugeot sert automatiquement de référence,
même si sa date précède le début de l'historique d'énergie. Le formulaire
« Pourcentage actuel confirmé » et la demande de confirmation ont été supprimés.
Aucune valeur manuelle ne remplace désormais la référence Peugeot.

L'estimation ajoute uniquement l'énergie mesurée par la borne depuis le premier
index disponible, selon la capacité utile et le rendement déjà configurés.
Exemple : Peugeot 75 %, capacité utile 40 kWh, rendement 100 %, puis 2 kWh
mesurés donnent 80 %. Une répétition du même ancien relevé ne réinitialise pas
l'estimation. Un relevé constructeur plus récent la recale, avec l'énergie connue
chargée depuis la date de ce relevé. L'arrêt sur l'objectif reste appliqué.

Les références manuelles enregistrées en 0.1.10 sont abandonnées au profit du
dernier relevé Peugeot. Les sessions, réglages, secrets et bilans sont conservés.
La dernière référence constructeur est persistée même reçue hors recharge ;
elle reste disponible après redémarrage et rebranchement pendant une panne du
cloud. Elle est isolée par véhicule/VIN et repart d'une nouvelle base d'énergie
à chaque branchement, sans reprendre les gains estimés de la session précédente.
Les mesures d'énergie perdues, remises à zéro ou incohérentes restent signalées ;
le correctif retire le refus lié à l'âge de la référence Peugeot.

L'énergie chargée et les trajets antérieurs au premier index disponible ne
peuvent pas être reconstruits. Le SOC reste une estimation à partir de la dernière
valeur Peugeot, comme demandé ; sa date reste affichée. Aucun essai matériel,
déploiement Portainer ou modification HA n'est effectué par l'assistant.

## Mise à jour Portainer

Image privée Linux amd64 : `ghcr.io/macorou/solar-energy-manager:0.1.11`.
Publication et digest : à renseigner après CI.

Dans la Stack existante, utiliser :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.11
```

Si le Compose utilise `SEM_VERSION`, passer cette variable à `0.1.11`.
Conserver le port `8090:8080`, le volume `/data`, les autres variables et
l'authentification GHCR existants. Télécharger la nouvelle image lors de la
mise à jour. Aucun nouveau paramètre ou pourcentage manuel à renseigner.

## Vérifications

Revue indépendante : un défaut important reproduit puis corrigé, concernant la
conservation de la référence entre redémarrage et nouvelle session sans cloud.
Les tests couvrent aussi une mesure reçue hors recharge et l'isolation entre VIN.
Aucun défaut mineur différé. Les règles existantes d'hystérésis de 1 % et de
verrouillage de l'objectif sont conservées. Les comportements réels de la borne
et de Peugeot restent à vérifier sur l'installation ; la revue ne les commande pas.

Résultats finaux de tests et publication : à compléter après CI.
