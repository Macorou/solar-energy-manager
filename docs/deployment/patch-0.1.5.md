# Patch 0.1.5 — connexion Ariston lors du changement de mode

L'essai manuel peut produire `unsupported_native_control`, puis « Demande 0 W ·
résultat inconnu » et « Arrêt demandé », bien que le test de connexion annonce
les commandes natives. Le changement de mode recréait la session Ariston ;
l'exécution avant initialisation pouvait mémoriser un rapport vide de capacités.

Ce patch conserve la session lors d'un changement de mode, d'armement ou de
réglages de pilotage, tout en appliquant la configuration courante. Une nouvelle
passerelle ou de nouveaux identifiants remplacent la session et invalident
l'ancien état connecté. L'initialisation et les commandes sont sérialisées ;
un rapport établi avant découverte ne bloque plus les commandes ultérieures.
Une initialisation interrompue reprend le chargement des limites, et les lectures
d'une ancienne session ne peuvent pas remplacer l'état de la session courante.

Le correctif ne modifie pas les modes de chauffe, les limites électriques,
les réservations ou la confirmation de l'effet physique. Les corrections 0.1.4
sur les puissances inchangées et l'ancien SOC sont conservées. Aucune migration
de données ni commande sur l'installation réelle n'est effectuée par l'assistant.

## Mise à jour de la Stack existante

Image publiée : `ghcr.io/macorou/solar-energy-manager:0.1.5`, privée, Linux amd64.

Digest : `sha256:e2cb287212f981d35fe592d389a5be36562d60cf63d37f7f8a33d6b7b37785b1`.

[Publication et contrôles réussis](https://github.com/Macorou/solar-energy-manager/actions/runs/40592551168)
pour le commit `686fc10bd3cfc35db9b69be711ac7b02c8ce403a` : tests logiciels,
quatre parcours navigateur, validation Compose, construction et test Docker de
démarrage/persistance/non-root, paquet privé et téléchargement authentifié vérifiés.

Conserver le nom de la Stack, le volume existant, le port **8090**, les accès et
les autres réglages. Modifier seulement `SEM_VERSION=0.1.5` si cette variable est
utilisée, ou la ligne `image: ghcr.io/macorou/solar-energy-manager:0.1.5`.
Redéployer avec téléchargement de l'image, puis actualiser complètement la page.
`/api/v1/health/live` et le bas du menu doivent indiquer **0.1.5**.

## Ancien résultat inconnu

La mise à jour conserve volontairement une commande inconnue et sa réservation.
Un redémarrage ne prouve pas son résultat et ne doit pas relancer la chauffe.

Après avoir vérifié sur le ballon ou dans Ariston NET qu'il est bien arrêté :

1. Dans la Vue d'ensemble, sélectionner **Pause** pour le ballon.
2. Dans **Eau chaude**, utiliser **Désactiver après arrêt** ; l'application exige
   une mesure électrique utilisable inférieure ou égale à 20 W. Cette procédure
   dédiée efface l'ancien résultat et sa réservation, sans modifier les accès.
3. Utiliser **Tester la connexion**, puis réactiver le pilotage avec les
   vérifications habituelles.
4. Faire un nouvel essai **Manuel** ou **Chauffer maintenant**. La demande est
   temporaire (30 minutes). Attendre au moins **60 secondes après le dernier
   ordre d'arrêt** avant ce départ : la temporisation native est conservée.
   Une acceptation n'est pas une preuve de chauffe :
   contrôler l'état du ballon et la montée de puissance.
5. Pour le fonctionnement habituel, choisir **HC/HP + solaire** dans
   **Eau chaude → Configurer → Mode**, puis enregistrer.

Si l'une des étapes est refusée, relever son message au lieu de modifier la base
de données ou de supprimer le volume. Aucun effacement manuel n'est nécessaire.

Retour possible à l'image 0.1.4 avec le même volume, sans migration.

## Vérifications logicielles

Seize nouveaux cas couvrent les changements de mode, consigne et identité,
l'initialisation concurrente/interrompue et les lectures de session périmées.
Les échecs ont été constatés avant les corrections. Résultat local : **103 tests
Python réussis**, un test Docker réservé au runner CI ; **20 tests UI réussis**,
schéma et build TypeScript/Vite vérifiés.

La revue indépendante a relevé deux problèmes importants de concurrence.
Ils sont reproduits par cinq cas supplémentaires puis corrigés, avec une
nouvelle exécution verte de la suite complète. L'essai matériel reste à effectuer.
