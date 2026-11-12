# Mise à jour 0.1.41 — Relevé en retard et limite de borne stable

## Problème

Le 12 novembre au soir, en 0.1.40, la charge a encore été suspendue une vingtaine de secondes à 22:52 :

1. **Relevé en retard.** La borne s'est mise d'elle-même en pause (SuspendedEVSE). 4,6 s plus tard, le Meross a publié un nouveau relevé qui indiquait encore 17,6 A sur L1, voiture comprise ; le Linky n'indiquait déjà plus que 2 A. La 0.1.40 considérait tout nouveau relevé comme à jour : elle a levé l'attente, vu la phase en surcharge et suspendu la voiture. Le relevé suivant (1,7 A) est arrivé 13 s plus tard.
2. **Limite de borne instable.** La limite envoyée à la borne suivait au dixième d'ampère le bruit de la maison sur L1 : elle changeait toutes les 10 à 30 s (17,5, 18,5, 17,9, 19,1 A…). Les deux pauses de la borne de la soirée sont arrivées moins d'une seconde après un tel changement.

## Changement

- Après un saut de puissance, un compteur n'est considéré comme relu qu'avec un relevé pris au moins 5 s après son premier nouveau relevé. La limite de 30 s reste inchangée.
- La limite de la borne reste calculée directement : limite de la phase − consommation de la maison − marge. Elle est envoyée en ampères entiers. Une baisse part immédiatement. Une hausse n'est envoyée que si elle apporte au moins 1 A et se maintient 60 s d'affilée.

En contrepartie, la voiture peut charger jusqu'à 1 A en dessous de la place disponible, et une hausse (y compris en mode solaire) arrive au plus tôt une minute après que la place s'est libérée.

## Portainer

Sauvegarder le volume /data comme habituellement, puis utiliser SEM_VERSION=0.1.41 ou ghcr.io/macorou/solar-energy-manager:0.1.41. Télécharger la nouvelle image et conserver le volume /data et les ports existants. Le schéma SQLite et les réglages ne changent pas.

**Retour en arrière :** la 0.1.40 démarre avec le même volume, sans restauration.

En venant d'une version antérieure à la 0.1.34, suivre aussi la [note 0.1.34](patch-0.1.34.md) : sa sauvegarde est nécessaire pour un retour en arrière.

Aucune commande matérielle n'a été envoyée pendant le développement. Le diagnostic s'appuie uniquement sur la lecture des journaux de SEM et de l'historique Home Assistant. Les essais utilisent un stockage jetable et des données fictives ; aucun historique, accès ni réglage de l'installation réelle n'a été modifié par ces tests. Le comportement avec la vraie borne n'est pas encore vérifié.
