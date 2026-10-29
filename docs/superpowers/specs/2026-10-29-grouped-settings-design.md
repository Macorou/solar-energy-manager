# Réglages en cartes regroupées

Direction validée le 29 octobre 2026 : l'utilisateur choisit l'aperçu « Cartes regroupées » et autorise l'implémentation. La maquette interactive est la référence visuelle ; les valeurs fictives sont remplacées par l'état réel du serveur.

## Choix et périmètre

La grille présente simultanément les équipements et leurs mesures, contrairement à l'alternative « Liste et détails ». Réglages comporte Équipements, Intégrations et Installation. Chaque carte ouvre une fenêtre avec les champs existants. Les intégrations utilisées sont Home Assistant, Peugeot, Ariston et le service OCPP ; aucun service fictif n'est ajouté. Les cartes réseau affichent les trois phases suivies. Les actions d'ajout et la configuration des véhicules restent disponibles.

Le thème sombre et le thème clair s'appliquent à toute l'application, avec un bouton soleil/lune en haut à droite, un choix conservé dans ce navigateur et un rendu adapté au téléphone. Les illustrations existantes restent identiques.

## Contraintes

- Réutiliser React, TypeScript et les API existantes, sans dépendance supplémentaire.
- Conserver les paramètres, associations de capteurs et champs avancés ; les secrets vides conservent les accès enregistrés.
- Ouvrir ou fermer une fenêtre ne sauvegarde rien. Les échecs restent visibles dans la fenêtre et ne la ferment pas.
- Le flux des mesures ne réinitialise pas un formulaire ouvert. Les mesures manquantes affichent « — », sans valeur de démonstration.
- La refonte ne modifie pas le moteur, les protections, les autorisations ou le contrôle physique des appareils.
- Le champ URL destiné à Wallbox contient la base `/ocpp/`, l'identifiant étant ajouté par la borne.
- Aucune publication, commande sur l'installation réelle ou modification du serveur dans cette étape.

## Mise en œuvre

Choix de réalisation : extraire les éditeurs déjà utilisés pour partager les mêmes champs entre les pages existantes et les fenêtres des cartes. Les métriques utilisent `/state` déjà actualisé par App ; l'état du service OCPP utilise son API existante. Les dialogues natifs assurent la fermeture au clavier, le focus et le défilement sur téléphone.
