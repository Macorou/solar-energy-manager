# Carte Maison — consommation totale et capteur HA facultatif

Choix utilisateur du28octobre : consommation totale du logement, voiture et
ballon inclus. Sa question demande aussi un paramètre pour associer un capteur HA.
Le contrôle UI actuel des dates fournisseur peut masquer des valeurs inchangées
pourtant vérifiées récemment ; reproduction locale :400W/0W relus ensemble donnent
null lorsque les dates fournisseur sont espacées,400W avec dates communes.

## Solution retenue

Ajouter `HomeAssistantConfig.house_entity`, chaîne vide par défaut, dans le
formulaire Home Assistant : « Entité consommation totale de la maison (facultatif) ».
Ce capteur représente la puissance totale du logement, voiture et ballon inclus,
en W ou kW. Il doit être un vrai capteur de consommation totale, pas l'échange
réseau signé si une production solaire peut alimenter la maison.

Avec un capteur configuré : afficher sa mesure valide, zéro inclus. Si ce capteur
est absent/indisponible/invalide, afficher « — » et ne pas changer silencieusement
de méthode. Sans capteur dédié : calculer réseau signé + production solaire,
sans soustraire les appareils. Les compteurs des appareils n'interviennent pas
dans cette consommation totale et leur absence ne doit pas la masquer.
Appairer les vérifications `checked_at` valides, avec `measured_at` en repli pour
les sources sans vérification. Conserver le seuil de cohérence2s et les refus
de données inutilisables/non finies, de dates invalides et de résultats négatifs.

## Architecture et alternatives

Un capteur obligatoire imposerait une configuration alors que le calcul est
possible. Un calcul unique ne permet pas d'utiliser le capteur demandé. Retenir
un capteur facultatif prioritaire et un calcul lorsque le champ est vide.
Transmettre `SiteSnapshot.house` et `house_configured` dans l'état public.
Ce nouvel échantillon sert seulement à l'affichage : ne pas l'ajouter aux budgets,
aux limites de puissance, à la liste de capteurs de contrôle obligatoires ou aux
confirmations de commandes. Une erreur de ce seul capteur n'arrête pas le pilotage.

Préserver anciens réglages, secrets, modes, consignes, armement, port et volume.
Même worktree/branche. Nouvelle image privée Linuxamd64. Aucun ordre réel,
changement HA ou déploiement Portainer par l'assistant.

## Vérifications

TDD : import/export, capteurs appareil absents, valeurs inchangées vérifiées,
dates réellement incohérentes, capteur dédié0W, valeurs invalides et absence de
repli silencieux. Test du formulaire et de sa persistance, lecture HA simulée,
état public, absence d'effet du capteur facultatif sur le contrôle. Revue unique,
suites complètes, schéma/build et CI navigateur/Docker avant publication0.1.8.
