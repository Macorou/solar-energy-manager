# Compte rendu de validation — 26 octobre 2026

Le logiciel livré est une première version à mettre en service. Il n’est pas encore validé sur l’installation physique.

| Vérification | Résultat et portée |
| --- | --- |
| Moteur et API | Tests automatisés des priorités, budget commun, réservations, nuages, états inconnus, accès administrateur, persistance et chiffrement. |
| Plannings | Récurrences, début la veille, changements d’heure, fin du complément à l’échéance, rejet de fenêtres réseau incompatibles et résultat d’échéance enregistré. |
| OCPP | Serveur WebSocket local : messages 1.6J, conversion W/A, transaction persistée et déconnexion. Aucun essai sur la Pulsar Plus. |
| Peugeot | HTTP simulé : OAuth, rotation des accès, refus et horodatage de batterie conservé. Aucun compte réel connecté. |
| Ariston | Appareil simulé : capacité absente refusée, limites de température et absence de fausse confirmation. NUOS Plus Wi-Fi non testé. |
| Home Assistant | Serveur WebSocket local et HTTP simulé : unités, signe, dates fournisseur, resynchronisation et indisponibilité après déconnexion. Aucune mesure de la maison utilisée. |
| Interface | Formulaires et parcours sur API temporaire : compte, véhicule, borne, ballon, programme à 80 % à 05:45, deux plages HC, simulation isolée ; captures 1920 et 390 px. |
| Conteneur/GHCR | 60 tests Python, 4 tests d’interface, 2 parcours navigateur, construction et smoke test Docker réussis sous Linux. Image 0.1.0 privée, digest téléchargé avec authentification, accès anonyme refusé et provenance vérifiée. |
| Portainer de l’utilisateur | Non déployé : adresse et accès au serveur non fournis. Architecture Intel/AMD64 confirmée ; Compose et guide livrés. |
| Installation physique | Non activée ; aucune commande envoyée au véhicule ou au ballon. |

## Paramètres à relever

- Architecture du serveur Portainer : Intel/AMD64 confirmé ; image Linux amd64.
- Mesure réseau signée, production solaire, puissance dédiée du ballon, cadence et convention de signe.
- Phases, courants minimal/maximal de la borne, puissance maximale du ballon et limite totale du site.
- Identité/authentification OCPP, VIN et passerelle Ariston ; saisir les accès uniquement dans l’application ou Portainer.
- Plages HC contractuelles et consigne sanitaire choisie.
- Demande et suspension natives, comportement hors ligne, expiration des profils OCPP et confirmation des arrêts.

## Scénarios matériels encore ouverts

Surplus pour un appareil puis pour les deux, arbitrage des priorités, passage nuageux, objectif de batterie le matin, chauffe en HC, manuel local, perte de HA/Peugeot/Ariston et redémarrage du conteneur avec une session en cours. Les tests automatisés couvrent les règles ; les essais matériels valident les particularités de l’installation.

L’intégration de retour Home Assistant et EDF Tempo restent des extensions après la base. Aucune modification de câblage ou de consigne sanitaire n’est implicite dans cette livraison.
