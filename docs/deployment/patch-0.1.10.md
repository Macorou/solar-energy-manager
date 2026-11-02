# Mise à jour 0.1.10 — recharge dynamique, bilan et batterie estimée

Version remplacée par **0.1.11** : la dernière valeur Peugeot sert désormais
automatiquement de référence et le formulaire de confirmation a été supprimé.
Voir [le guide 0.1.11](patch-0.1.11.md). Le texte ci-dessous décrit la version 0.1.10.

## Installation dans Portainer

Image privée publiée : `ghcr.io/macorou/solar-energy-manager:0.1.10` (linux/amd64).

Digest immuable :
`sha256:196a42f4e7259e8e00ad54a316a43df88c739d60fb732bea2e152cf3b41d3d7b`.

Code livré : `b8f87041855d33f2d8772305c7119e094d5cc2fc`, tag `v0.1.10`.
[Construction et vérifications réussies](https://github.com/Macorou/solar-energy-manager/actions/runs/40755012215).

Dans la Stack existante, modifier uniquement le tag de l'image, ou passer la
variable `SEM_VERSION` à `0.1.10` si la ligne utilise cette variable. Conserver
`SEM_HTTP_PORT=8090` ou le mapping existant `8090:8080`, le volume monté sur
`/data`, les variables et les accès GHCR déjà configurés. Choisir le téléchargement
de l'image dans la mise à jour de la Stack. Ne pas supprimer le volume ni recréer
le compte administrateur. Une sauvegarde du volume permet le retour arrière.
L'assistant ne déploie pas cette mise à jour et ne commande aucun appareil réel.

## Ce qui change

- Puissances en W sous1000W, en kW dès1000W, signe d'injection conservé.
- Courants des trois phases visibles et courant de recharge limité sur la phase
  réellement utilisée. Les limites globales et le plafond3700W restent appliqués.
- État voiture branchée/en charge/en attente/terminée/débranchée, distinct de la
  connexion de la borne et du mode Observation.
- Énergie de recharge, coût cumulé, pourcentage solaire estimé, prix effectif
  instantané et prix moyen de session.
- Pourcentage de batterie estimé avec les kWh de la borne, utilisé pour demander
  l'arrêt à la cible, puis recalé sur une mesure Peugeot plus récente.

## Mesures réseau et limitation par phase

La mise à jour n'active pas automatiquement la limitation. Dans **Réglages →
Home Assistant · mesures**, utiliser **Suivre L1/L2/L3**, puis associer pour chaque
phase le courant A/mA et, facultativement, tension V et puissance signée W/kW.
Les VA du Linky sont une puissance apparente, pas des W : ne pas les associer
au champ de puissance active. Les noms de capteurs ne garantissent pas le câblage.
Renseigner la limite de courant de chaque phase selon l'installation ; les20A
proposés à la création d'une ligne sont modifiables et ne valent pas validation.
Enregistrer Home Assistant ; laisser le champ jeton vide conserve son accès.

Dans **Voiture → Configurer**, sélectionner **Phase réseau utilisée**. Pour
l'e208 monophasée, choisir la phase qui correspond à L1 côté prise/borne, même
si la Wallbox est triphasée. Pour un véhicule triphasé, l'ordre des phases relie
les phases OCPP L1/L2/L3 au réseau. La modification des caractéristiques matérielles
d'une borne déjà activée passe par la désactivation dédiée après arrêt.

Dans **Réglages → Installation**, choisir la marge en A puis activer **Limiter la
recharge par phase** et enregistrer. Les mesures doivent être disponibles avant
l'activation. Le courant réel de la voiture doit être transmis par OCPP
`Current.Import` (A/mA), en plus des mesures réseau. Le logiciel ne modifie pas
automatiquement la configuration interne de la Wallbox pour forcer ces trames.
Si elles manquent pendant la charge, le motif indique le courant réel indisponible
et le contrôleur suspend ; il ne prend pas le courant commandé pour une mesure.

Le principe de limitation est adapté d'EVCC : ajouter au courant réel de la voiture
seulement la marge restante de la phase, réserver les ordres non encore observés,
arrondir vers le bas et suspendre sous le courant minimal. Baisse prioritaire
sans délai nuage, en manuel comme en automatique. Les délais HA/OCPP subsistent ;
le contrôleur agit sur la recharge et ne remplace pas les protections électriques
ni ne coupe les autres consommateurs d'une phase indépendante de la voiture.

Source : [EVCC circuit.go](https://github.com/evcc-io/evcc/blob/9404d825d6a659d8ce7f47d3b0d2e14ac04506e0/core/circuit/circuit.go).
Notice MIT conservée dans `docs/third-party/evcc-MIT.txt` et `/opt/sem/licenses`
dans l'image. Adaptation par phase, sans service EVCC supplémentaire à installer.

## Tarif et bilan de recharge

Configurer **Entité prix actuel du réseau (€/kWh)** dans les mesures HA.
Le capteur vérifié pour cette installation est `sensor.prix_electricite_actuel` ;
le logiciel ne l'associe pas automatiquement. Un tarif inchangé reste utilisable
lorsque HA confirme actuellement sa disponibilité. Un champ manquant ne vaut
pas0€ et ne bloque pas les commandes de recharge.

Dans Installation, **Coût du solaire autoconsommé (€/kWh)** vaut0 par défaut,
modifiable. Le prix effectif est le mélange estimé du réseau et du solaire
autoconsommé dans le logement ; le solaire exporté n'est pas attribué à la voiture.
La part solaire est une attribution proportionnelle au logement, pas une mesure
physique de l'origine de l'électricité sur le câble ou sur la phase de l'e208.

Les index OCPP Wh/kWh, début et fin de transaction, alimentent la session de
branchement. Les pauses/reprises ne remettent pas les kWh à zéro. Le coût cumule
les contextes tarifaires au fil du temps : un nouveau tarif ne remplace pas le
coût passé. Entre deux index, l'allocation temporelle suppose une charge uniforme.
Le coût est donc estimé et ne remplace pas une facture. Les recharges antérieures
à ce suivi ne sont pas reconstruites. Un tarif/mix manquant ou un compteur réinitialisé
est signalé par un bilan partiel/inconnu, jamais un coût total fictif à0€.
La session est persistée et la dernière reste visible après débranchement.

## Batterie et objectif

Dans **Voiture → Véhicules → Modifier**, renseigner la **capacité utile connue**
et le **rendement de charge (%)**. Ne pas recopier une capacité brute commerciale
sans vérifier sa correspondance ; aucune capacité n'est déduite du seul modèle2020.
Le rendement commence à90% et peut être ajusté.

SOC estimé = SOC de référence Peugeot +100 × énergie AC chargée × rendement /
capacité utile. L'estimation est utilisée pour demander l'arrêt à l'objectif
en solaire, planifié et manuel avec véhicule associé. La réception répétée du
même ancien SOC ne réinitialise pas l'estimation. Une mesure plus récente recale
la référence à sa date en tenant compte de l'énergie chargée depuis cette date.
La jauge indique sa nature estimée et conserve la date du relevé constructeur.

Sans capacité/index fiable, un ancien SOC seul n'autorise pas une poursuite
indéfinie. Une perte d'énergie ou une valeur de compteur impossible entraîne une
estimation à vérifier ; une nouvelle mesure constructeur permet un recalage.
La cible reste mémorisée pour éviter une reprise sur une ancienne valeur relue ;
une cible relevée explicitement, ou une mesure réelle plus récente dépassant
l'hystérésis1% sous la cible, peut permettre une nouvelle recharge autorisée.
La précision dépend de la capacité, des pertes et des arrondis ; ce n'est pas une
mesure garantie au pourcentage exact. Les limites natives du véhicule restent actives.

Si le premier relevé Peugeot est plus ancien que l'historique d'énergie suivi,
le logiciel ne peut pas savoir ce qui s'est passé entre-temps. La carte propose
**Pourcentage actuel confirmé (%) → Confirmer pour cette recharge**, après
vérification du niveau actuel sur la voiture. Cette confirmation exige une
capacité utile renseignée, un véhicule branché et un index d'énergie récent ;
elle appartient seulement à ce branchement et n'est pas réutilisée après un
trajet/débranchement. Une nouvelle mesure Peugeot couverte par l'historique
peut aussi fournir la référence automatiquement. **Actualiser le compteur de la
borne** demande uniquement une publication OCPP MeterValues (TriggerMessage),
sans démarrer la charge ni changer le courant. La borne peut refuser cette
lecture si elle ne prend pas en charge RemoteTrigger ; l'interface le signale.

Les mesures réseau et courant voiture asynchrones n'autorisent pas une hausse
de courant. Une autorisation existante peut être maintenue ou réduite ; la
réservation ne crédite pas une ancienne mesure de courant après une suspension.
Les index par phase sont agrégés seulement s'ils forment un ensemble complet,
avec priorité à l'index total lorsqu'il est fourni. La fin de recharge peut être
reconciliée avec l'index terminal tardif ; tant qu'il manque, le bilan reste partiel.

## Choix de conception et limites vérifiées

- Solaire initialement0€/kWh, modifiable ; phase physique laissée à renseigner.
- Attribution proportionnelle au logement et charge uniforme entre index :
  estimations assumées, pas une facturation physique par phase.
- Source hors historique : référence utilisateur limitée à la session ou nouvelle
  mesure constructeur, plutôt que reprise implicite d'un ancien pourcentage.
- Trames de courant décalées : pas de hausse, maintien/réduction possible ; ce
  choix peut différer une augmentation jusqu'à réception de mesures cohérentes.
- Une baisse réelle de SOC constructeur de plus de1% peut rouvrir un objectif
  atteint ; les anciennes valeurs répétées ne le peuvent pas.
- Les conventions physiques de phases/courants Wallbox, les réponses réelles
  aux profils et les facteurs de puissance demandent un essai matériel distinct.
- Les intervalles de compteur longs utilisent les contextes disponibles ; les
  périodes sans contexte valide restent non attribuées, sans seuil d'intervalle
  global arbitraire ajouté. Plus les index sont espacés, plus l'allocation est approximative.
- Les conventions OCPP de phase locale restent à vérifier sur la borne réelle.
  Une phase manquante n'est pas inventée à partir du courant commandé.
- L'ancienne session reste affichée après débranchement ; elle ne décrit pas
  les évolutions de batterie après le départ du véhicule.
- Les dictionnaires de base de données délibérément altérés ne constituent pas
  une migration prise en charge ; les réglages des versions publiées conservent leurs défauts.
- La source/notice MIT EVCC a été lue en ligne par l'auteur ; la revue indépendante
  du code n'est pas une consultation juridique ni un nouvel audit amont.
- Publication Docker et rendu des captures sont vérifiés séparément de la
  revue de logique. Aucun résultat logiciel ne vaut essai de l'installation réelle.

## Contrôles de livraison

Vérification finale du tag : Python 230 réussis / 1 test Docker ignoré dans la
suite ordinaire puis exécuté séparément avec succès ; UI 42 ; navigateur 6 ;
Docker 1, schéma/types/build et Compose réussis. Les parcours navigateur passent
aussi localement, dont l'affichage 320/390/1280 px et le formulaire de référence SOC.
Le job de publication vérifie le paquet privé, le téléchargement authentifié
par digest et le refus d'un téléchargement anonyme.

Revue indépendante : six défauts importants corrigés avec reproductions puis
tests ; le décalage du but affiché en manuel a aussi été corrigé. Un dernier
cas de planning distingue SOC brut ancien non suivi et estimation fiable ; il
est inclus dans 0.1.10. L'image 0.1.9 intermédiaire reste immuable ; utiliser 0.1.10.
Aucun point mineur différé. Les choix et limites de calcul figurent ci-dessus.

Aucun essai matériel du nouveau limiteur, du suivi de coût ou du SOC estimé,
ni aucun déploiement Portainer, effectué par l'assistant. La branche de travail
et la PR en brouillon existantes sont conservées ; aucune fusion dans main.
