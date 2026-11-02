# Correction de l’interface — 0.1.1

Le tableau de bord livré dans 0.1.0 s’éloignait du concept initial. La correction reprend la photo de référence fournie le 27 octobre : barre latérale bleu nuit, quatre indicateurs Réseau / Voiture / Eau chaude / Maison, deux cartes illustrées avec jauges et commandes, planning en bandes et carte Home Assistant. Les illustrations vectorielles sont originales ; la composition suit la référence, sans revendiquer l’identité exacte de son dessin de voiture.

## Revue indépendante

Revue en lecture seule de `c2ddb9c..36099fd`, avec comparaison de la photo et des captures 1280 / 390 px. Aucun point critique ou mineur ; deux problèmes importants reproduits puis corrigés en une passe.

| Point | Correction et preuve |
| --- | --- |
| Le sélecteur Automatique pouvait perdre le mode planifié ou HC/HP | La reprise conserve un mode automatique déjà actif, restaure celui enregistré avant le manuel ou la pause, et retire le minuteur manuel. Neuf cas API couvrent ces transitions et le maintien des refus d’activation/résultat inconnu ; cinq échouaient avant correction. |
| Le résumé des programmes voiture traversant minuit pouvait décaler la nuit d’un jour | Les jours voiture sont explicitement ceux de l’échéance ; le début est la veille. Les jours HC restent ceux du début, avec fin le lendemain. Test de rendu lundi uniquement vu en échec puis en réussite. |

La vérification supplémentaire des largeurs 320, 390, 768, 801, 980, 1024, 1280, 1440 et 1920 px a révélé des boutons trop serrés autour de 801 px et le dernier libellé d’axe dépassant sa carte. La disposition intermédiaire empile maintenant les appareils ; le dernier repère horaire reste dans la carte. Le contrôle de débordement a été repris dans le parcours navigateur.

## Décisions d’exécution

1. La référence et la demande explicite de correction fixent le résultat visuel ; ne pas rouvrir les choix de produit déjà tranchés. Coût si la lecture est erronée : ajustement visuel à refaire après réaction de l’utilisateur.
2. Réutiliser le worktree séparé autorisé et l’exécution directe ; conserver un journal natif équivalent aux scripts Bash incompatibles sous Windows. Coût : suivi manuel du processus local.
3. Afficher les plages configurées plutôt qu’une durée optimisée inventée, et masquer le bilan Maison lorsqu’une mesure manque ou n’est pas cohérente. Coût : quelques légendes supplémentaires et des tirets avant la disponibilité de toutes les mesures.
4. Corriger la reprise Automatique dans la route existante bien que le défaut la précède : le nouveau sélecteur doit conserver les politiques choisies. Coût : extension limitée du correctif au traitement de cette transition, sans modification du moteur énergétique.

## Limites assumées

- Wallbox, Peugeot, Ariston et Portainer réels restent à valider sur place ; aucun connecteur réel ni commande matérielle n’est utilisé par les tests.
- Les captures de comparaison sont issues du véritable frontend avec des réponses de test isolées et portent « MAQUETTE · DONNÉES FICTIVES ». Une capture de l’état réel non connecté est également fournie.
- Les neuf largeurs citées sont vérifiées ; cela ne garantit pas chaque combinaison de taille, police et nom extrême. Les noms d’appareil longs peuvent se répartir sur plusieurs lignes et les noms de programme sont tronqués visuellement avec leur détail conservé dans les réglages.
- Le dessin local n’est pas une reproduction exacte du véhicule de la photo. Il ne nécessite ni réseau ni image externe.

## Vérifications

Après correction : 69 tests Python réussis et 1 test Docker réservé à Linux CI ; 11 tests frontend réussis ; construction TypeScript/Vite réussie. Les trois parcours navigateur couvrent la configuration, l’origine HTTP LAN et le rendu de référence isolé avec les largeurs supplémentaires. Sous Windows, les cas réussissent mais la fermeture du serveur de test nécessite d’arrêter la session de test possédée ; Linux CI vérifie la fin complète du parcours et le conteneur avant publication.

L’intégration de retour vers Home Assistant et EDF Tempo restent prévues après validation de la base.

## Contrôle Linux et version publiée

Le tag de préparation v0.1.1 a échoué avant publication : à 320 px, la police de repli Linux donnait une navigation de 325 px. Aucun conteneur 0.1.1 n’a été publié par ce workflow. Le dépassement a été reproduit sous Windows avec Verdana : les boutons « Eau chaude » et « Réglages » agrandissaient les colonnes de navigation. Les colonnes mobiles utilisent maintenant minmax(0, 1fr), et les icônes passent au-dessus du texte sur les très petits écrans. Le scénario Verdana est ajouté au parcours. La livraison finale utilise 0.1.2, sans déplacer le tag v0.1.1 déjà enregistré. Le dessin, les commandes et la composition restent ceux validés pendant cette revue.

Le stress Verdana a aussi confirmé que les valeurs en kW devaient disposer de davantage de largeur dans les indicateurs à 320 px. Les marges, icônes et chiffres y sont ajustés, sans changer la composition de bureau. Après correction : 69 tests Python réussis (1 Docker en attente de CI), 11 tests frontend réussis, 3 parcours navigateur réussis avec les neuf largeurs et le stress de police, construction réussie.

Publication finale 0.1.2 réussie : [workflow complet](https://github.com/Macorou/solar-energy-manager/actions/runs/40460638853), commit `6c1f9375a0e898639a6302b3b189ed6e56936a35`. Les tests Linux, le smoke test Docker, la construction amd64, la publication privée, le téléchargement authentifié du digest, le refus anonyme et le label de provenance sont confirmés.
