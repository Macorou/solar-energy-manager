# Mise en service Ariston

Bibliothèque : `ariston==0.19.9`, projet [python-ariston-api](https://github.com/fustom/python-ariston-api), licence MIT. Cette bibliothèque distingue notamment Nuos Split et d’autres types Velis. La détection du modèle exact NUOS Plus Wi-Fi reste à effectuer avec le compte réel.

Saisir le compte dans Connexions, puis l’identifiant de passerelle dans le ballon. Le test lit les données principales et vérifie les méthodes disponibles. Il ne lance pas de chauffe. La lecture des paramètres de température est indépendante des diagnostics optionnels ; aucun appel au diagnostic `bus_errors` n’est nécessaire.

L’autorisation native marche/arrêt passe par `async_set_power`, la consigne par `async_set_water_heater_temperature`. Aucun relais de coupure électrique n’est utilisé. Une réponse à une commande est seulement une acceptation ; la lecture suivante doit confirmer la consigne/l’état, et la puissance réelle provient d’un capteur Home Assistant dédié. L’horodatage cloud affiché indique l’heure de lecture lorsque le fournisseur ne fournit pas d’heure de mesure.

Renseigner une puissance maximale prudente couvrant les modes natifs possibles, la consigne, les temporisations anti-cyclage et la mesure électrique du ballon. Le moteur réserve cette puissance entière ; il ne prétend pas moduler le compresseur du NUOS. Les protections, cycles sanitaires et consommations imposés par le fabricant restent prioritaires et doivent être inclus dans la limite du site.

Avant activation, vérifier sur place une demande de chauffe, une suspension native, les délais réels et le comportement en perte du cloud/conteneur. Si le modèle ne permet pas ces commandes, le laisser en observation. Les anciennes erreurs de diagnostic Home Assistant ne prouvent ni une panne actuelle ni la compatibilité du modèle.

**Validation :** tests simulés du connecteur ; aucun essai physique effectué à ce stade.
