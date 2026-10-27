# Correction visuelle du tableau de bord

Référence explicite : photo fournie par l’utilisateur le 27 octobre 2026. L’utilisateur demande de reprendre cette composition plutôt que celle livrée dans la V1.

- Barre latérale bleu nuit étroite, navigation claire et sélection bleue ; titre « Pilotage énergie », date et heure.
- Quatre indicateurs compacts : Réseau, Voiture, Eau chaude, Maison. La production solaire reste visible dans une ligne de contexte.
- Deux cartes principales blanches, de même importance : illustration vectorielle détaillée d’une voiture blanche et d’un ballon cylindrique, grande mesure, jauge bleue ou orange, objectif, commandes Automatique / Manuel / Pause et bouton de démarrage bleu ou orange.
- Planning en bandes bleues et orange et carte Home Assistant en bas. Les bandes représentent les créneaux configurés, jamais une durée de chauffe ou de charge calculée fictivement.
- Maison est un bilan calculé hors appareils pilotés : solaire + réseau signé − appareils. Il n’est affiché que si les mesures sont utilisables, finies et cohérentes dans une fenêtre de 2 secondes. Les mesures absentes restent « — ».
- L’état affiché vient des observations ; une commande acceptée ne devient pas une confirmation. Les appareils non activés conservent leurs commandes désactivées.
- Conserver les écrans, les connexions, les règles de pilotage et l’adaptation mobile existants. Pas de dépendance supplémentaire ; illustrations SVG internes et locales.

Approche retenue : corriger les composants React et le CSS de l’application existante. Une image de fond statique ne fournirait ni commandes accessibles ni mesures réelles ; une nouvelle application dupliquerait inutilement le système existant. Le brief et sa référence sont fournis directement par l’utilisateur, sans choix de produit restant à demander.

Validation : tests des valeurs dérivées et des commandes, construction TypeScript, parcours navigateur de configuration, captures à 1280 et 390 pixels comparées à la référence. Livrer une image Docker 0.1.1 distincte de 0.1.0, avec Compose mis à jour.
