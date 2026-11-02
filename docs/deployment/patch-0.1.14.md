# 0.1.14 — cinq minutes pour la première puissance de recharge

Diagnostic réel en lecture seule : départ accepté à22:19:37UTC, arrêt à22:21:07UTC,
soit90s après. Le courant OCPP est bien remonté à16,9A ; le capteur HA de puissance
est resté à0W avec son ancienne date. Le délai de confirmation était trop court.

Correctif ciblé :
- Attente minimale de confirmation de puissance portée à300s pour la voiture.
- Première remontée de courant : délai porté de30 à300s, sans hausse du profil.
- Renouvellement du même profil OCPP pendant cette attente, sans rejouer un départ.
  La durée initiale de cinq minutes ne repart jamais à zéro au renouvellement.
- Les mesures apparues entre le départ et le renouvellement peuvent confirmer
  la charge. Les défauts de communication et les limites électriques continuent
  de provoquer un arrêt immédiat. Une absence de confirmation après cinq minutes
  provoque toujours un arrêt. Pause, fin de planning et objectif restent prioritaires.

Tests :293Python réussis,1Docker ignoré localement ;42UI, schéma et build réussis.
Pas de déploiement ni de commande réelle. Cette version est préparée localement ;
la construction Docker et les contrôles Linux seront effectués par GitHub après
le push du tag. Aucun push automatique par l’assistant pour cette version.

## Publication par l’utilisateur

Le commit et le tag`v0.1.14` sont déjà créés localement. Dans PowerShell sur le PC
Windows qui contient le projet :

```powershell
Set-Location 'C:\Users\jorda\Documents\Codex\2026-10-26\en\outputs\solar-energy-manager\.worktrees\v1'
git push origin feat/v1-energy-manager-impl refs/tags/v0.1.14
```

Ouvrir https://github.com/Macorou/solar-energy-manager/actions et attendre que
le workflow **Publish private container** du tag`v0.1.14` soit vert. Il teste,
construit et publie automatiquement l’image privée Linux amd64. Aucun build
Docker local ou commande manuelle de publication GHCR n’est nécessaire.

Dans Portainer, utiliser ensuite :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.14
```

Ou définir`SEM_VERSION=0.1.14`. Mettre à jour la Stack en téléchargeant l’image,
en conservant le volume`/data`, le port et les paramètres existants.

Si un ancien résultat inconnu reste bloquant après mise à jour, vérifier que la
borne est réellement arrêtée, puis utiliser Pause, Désactiver après arrêt,
Tester la connexion et Activer le pilotage. Le correctif ne supprime pas
aveuglément les défauts déjà enregistrés. Un planning actif peut relancer la charge.
