# Mise en service OCPP — Wallbox Pulsar Plus

État initial : protocole testé avec des échanges simulés, pas encore sur la borne de l’installation.

Enregistrer la borne et son identifiant dans l’interface avant de configurer son serveur central. L’URL attendue est `ws://ADRESSE_DU_SERVEUR:PORT/ocpp/IDENTIFIANT` ou son équivalent WSS derrière un reverse proxy compatible. Dans une interface Wallbox qui ajoute elle-même l’identité, saisir la base `/ocpp/` et le même identifiant dans le champ dédié, puis vérifier l’URL effective.

OCPP 1.6J est requis. Configurer si disponible l’authentification Basic avec identité et mot de passe dédié. Une connexion sans mot de passe est refusée par défaut ; l’option explicite d’identité seule concerne exclusivement un réseau local de confiance. Aucun accès public automatique n’est prévu.

Relever référence, firmware, phases, courant minimal/maximal et rythme des mesures. Tester la lecture de `SupportedFeatureProfiles`, la limitation du courant, les refus, l’arrêt de transaction et la reconnexion. Un profil accepté ne prouve pas que sa limite est appliquée. L’expiration du profil ne garantit pas l’arrêt : le comportement natif hors ligne doit être testé et confirmé avant l’activation solaire.

Inventorier les horaires et contrôles concurrents dans Wallbox, Peugeot et Home Assistant. Le nouveau moteur doit rester le seul décideur automatique. Les demandes de charge sont autorisées par des permissions courtes émises par le moteur ; un badge n’accorde pas une charge permanente indépendante des plannings.
