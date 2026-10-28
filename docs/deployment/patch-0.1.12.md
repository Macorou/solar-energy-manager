# Mise à jour 0.1.12 — compteur au démarrage de la recharge

Version complétée par [0.1.13](patch-0.1.13.md) pour le premier courant OCPP
et la confirmation d’arrêt lorsque le0W HA reste inchangé.

Le planning autorisait bien la recharge à 80 % pour 05:45. Le diagnostic en
lecture seule de 0.1.11 a trouvé une référence Peugeot de 60 % disponible,
mais un suivi d'énergie partiel sans Wh compté qui rendait le SOC inutilisable.
Le journal montrait un démarrage accepté, puis un arrêt trois secondes après.
L'ancien index précédant cette transaction n'a pas été conservé dans le journal ;
le changement de base a été reproduit localement et son chemin de blocage identifié.

## Correction

- Le début de transaction OCPP apporte maintenant son identité, sa date et son
  index de départ au suivi. Un changement de base entre deux transactions ne
  devient pas une énergie chargée fictive et ne supprime pas le SOC Peugeot.
- Les Wh déjà comptés pendant le branchement sont conservés entre transactions
  et redémarrages ; la répétition d'une trame n'ajoute pas l'énergie deux fois.
- Une ancienne session bloquée par ce défaut avant le premier Wh peut reprendre
  uniquement après confirmation de l'arrêt par une mesure électrique utilisable
  de 0 W (tolérance20 W). Le bilan concerné reste marqué partiel.
- Un compteur absent, ancien ou incohérent pendant une charge suivie garde son
  contrôle ; son motif identifie désormais le compteur plutôt que la batterie.
- La référence reste exclusivement le dernier relevé Peugeot, sans saisie manuelle.
  La limitation par phase et l'arrêt sur l'objectif estimé restent appliqués.

Les périodes et énergies non observées ne sont pas inventées. Le SOC calculé et
les coûts restent des estimations lorsque le bilan est partiel. Les hypothèses
de répartition solaire et de rendement des versions précédentes s'appliquent.

La configuration réelle est conservée, notamment les valeurs que l'utilisateur
a modifiées depuis les premières versions. Aucune modification HA, commande
de borne, reconfiguration OCPP ou installation sur le serveur n'a été effectuée.
La limitation par phase exige toujours des données de courant de recharge
utilisables : le correctif ne remplace pas ces mesures par un courant commandé.

## Portainer

Image privée Linux amd64 publiée : `ghcr.io/macorou/solar-energy-manager:0.1.12`.
Digest immuable : `sha256:a910e54a090f9cf365ebaa6700733e01c39e1abf41aadca79859952a5ab3619b`.
Code livré : `97e2688e857fe163bc1aae92d0e770adf7d80428`, tag `v0.1.12`.
[Workflow de validation et publication](https://github.com/Macorou/solar-energy-manager/actions/runs/40774394475).

Dans la Stack existante :

```yaml
image: ghcr.io/macorou/solar-energy-manager:0.1.12
```

Ou passer `SEM_VERSION` à `0.1.12`. Conserver le port8090, le volume `/data`,
les variables et l'authentification GHCR existants ; télécharger la nouvelle
image lors de la mise à jour. Ne pas recréer le compte ou effacer les données.

## Validation

Revue indépendante : deux cas importants corrigés, concernant un index inférieur
au départ déclaré d'une transaction et la reprise d'une transaction d'une ancienne
version. Le motif d'un index devenu ancien après recalage Peugeot a aussi été
corrigé ; aucune anomalie mineure différée. Les cas ont échoué avant correction
puis passé les tests. La récupération d'un ancien défaut à0Wh ne neutralise pas
un nouveau défaut associé à une transaction identifiée.

Contrôles locaux finaux :248 tests Python et42 tests UI réussis ; schéma,
TypeScript/build réussis. Six parcours navigateur ont été exécutés localement,
puis sont rejoués par GitHub sur le tag final. Le test du coordinateur utilise un
adaptateur simulé et les mesures anonymisées du cas observé ; il produit un ordre
à3910W avec la limite par phase, sans commander la vraie installation.

Le tag final a passé **248 tests Python, 42 tests d'interface, 6 parcours navigateur
et 1 test Docker**, ainsi que les contrôles du schéma, TypeScript, build et Compose.
Le test Docker est ignoré dans la suite ordinaire puis exécuté séparément.
La publication a vérifié le paquet privé, son téléchargement authentifié par
digest et le refus d'une demande anonyme. Le workflow référencé ci-dessus est
terminé avec succès. Aucun test logiciel ne vaut validation matérielle de cette
reprise sur la Wallbox réelle ; le serveur n'a pas été mis à jour par l'assistant.

La branche existante, le worktree et la PR en brouillon sont conservés.
Aucune fusion dans main.
