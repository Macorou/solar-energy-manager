# Mise à jour 0.1.13 — courant OCPP et confirmation d’arrêt

Ce correctif traite le départ accepté puis interrompu pour « Courant réel de
recharge indisponible », et l’arrêt qui reste en attente lorsque le capteur HA
est toujours à 0 W avec une ancienne date de changement.

## Constat vérifié

Le serveur 0.1.12 a accepté 3 910 W, puis envoyé un arrêt sept secondes après.
Le planning autorisait le réseau et le SOC 60 % était utilisable. Les trois
courants réseau HA étaient disponibles ; les courants OCPP de la borne étaient
vides. Le message « Arrêt demandé » remplaçait ensuite le vrai motif de blocage.
Aucune action réelle n’a été effectuée par l’assistant pendant le diagnostic.

## Changements

- Lors d’un nouveau départ autorisé avec limitation par phase activée,
  l’application lit les paramètres de mesure OCPP, conserve les mesures déjà
  configurées et ajoute `Current.Import`, `Power.Active.Import` et
  `Energy.Active.Import.Register` si nécessaire. Elle règle un intervalle de
  dix secondes au maximum et relit les valeurs avant de démarrer.
- Un refus, une impossibilité de configuration ou une demande de redémarrage
  empêche le départ et affiche le problème. Aucun redémarrage de borne,
  changement de disponibilité ou changement de limite matérielle n’est envoyé.
- Pendant les trente premières secondes, l’attente du premier courant peut
  maintenir ou réduire le profil déjà autorisé, sans l’augmenter. Une mesure
  réseau absente, une surcharge ou un courant qui manque après ce délai garde
  son effet de réduction ou d’arrêt immédiat. Une perte de courant pendant une
  charge déjà mesurée ne reçoit pas un nouveau délai.
- Un état OCPP d’arrêt postérieur à la commande, sans transaction ni départ en
  attente, et une puissance HA 0 W vérifiée après cet état peuvent confirmer
  l’arrêt. La date du dernier changement HA n’a pas à évoluer. Cela ne confirme
  jamais un démarrage. Une relecture de l’état est demandée une fois pour
  réconcilier un arrêt, y compris après redémarrage de l’application.
- Le motif précis reste affiché pendant la vérification ; il ne devient plus
  simplement « Arrêt demandé » lorsqu’il s’agit d’une attente interne.

Cette préparation de la télémétrie suit le principe observé dans la
[configuration OCPP d’EVCC](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/charger/ocpp/cp_setup.go).
Le code Python est propre à ce projet. La notice MIT déjà présente pour le
limiteur adapté d’EVCC est conservée.

## Installation Portainer

Dans la Stack existante, remplacer uniquement l’image :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.13
```

Ou définir `SEM_VERSION=0.1.13`. Conserver port 8090, volume `/data`, accès privé
GHCR et tous les réglages actuels. Choisir le téléchargement de la nouvelle
image lors de la mise à jour de la Stack. Ne pas supprimer le volume.

La mise à jour conserve les appareils armés et leurs modes. Si le planning
autorise toujours la charge, celle-ci peut reprendre après réconciliation de
l’arrêt et vérification des paramètres de télémétrie. Il n’est pas nécessaire
de désactiver la limitation par phase ou de modifier la valeur Peugeot.

## Vérification sur la borne

Vérifier le journal, puis le passage en charge et la présence de courants
OCPP dans `/api/v1/state`. Le délai de trente secondes n’est pas une preuve
de courant : sans mesure exploitable, l’application suspend de nouveau et
conserve le motif précis. Si la borne refuse un paramètre ou demande un
redémarrage, conserver ce message pour le diagnostic ; l’application ne la
redémarre pas automatiquement.

Les essais logiciels utilisent des échanges OCPP simulés et du stockage local.
L’acceptation des paramètres et le fonctionnement physique sur cette Wallbox
restent à vérifier après installation. L’assistant ne déploie pas la Stack et
n’envoie aucun ordre à la voiture ou au ballon.

Validation locale : 289 tests Python réussis et 1 test Docker réservé à la CI ;
42 tests d’interface et 6 parcours navigateur réussis, schéma et build valides.
La revue indépendante a identifié trois points importants, reproduits avant
correction puis corrigés avec tests : conservation des anciennes mesures à la
relecture, preuve native obligatoire même pour un 0 W récent, et plafond/délai
maintenus durant l’état Preparing. Aucun point mineur différé.

## Publication vérifiée

Le tag`v0.1.13` correspond au commit
`d431033e28aabcda9f757fdbb01678e30b8acb51`.
Le [workflow40778390398](https://github.com/Macorou/solar-energy-manager/actions/runs/40778390398)
est terminé avec succès :289Python,42UI,6navigateur,1Docker, schéma/build/Compose.
Le paquet est privé, le téléchargement authentifié par digest est vérifié et
le téléchargement anonyme est refusé.

Digest de l’image Linux amd64 :
`sha256:3189803e4ebd4c1218e356fcb8b11babd78f137bc2a7db53a442fc19b4b91c5e`.

Les contrôles de publication sont distincts de la revue du logiciel. Le suivi
temporaire du plan a été adapté à PowerShell pour les permissions Windows,
sans effet sur le produit. La branche, le worktree et la PR en brouillon sont
conservés ; aucune fusion dans main ni intervention sur l’installation.
