# Dessins originaux du concept — 0.1.3

À la demande explicite de l’utilisateur, la voiture et le ballon affichent les dessins exacts du concept initial. Les interprétations vectorielles de 0.1.2 sont remplacées par des vues cadrées de l’image originale `docs/assets/pilotage-energie-concept-v1.png`.

Le fichier embarqué dans le frontend est une copie inchangée de cette image : SHA-256 `abbf7fd72b08eb0d3674891d92da47b95f7ce2625e286de5d69c0aaf4c88bb8c`, dimensions 1586 × 992 pixels. Les vues SVG montrent uniquement la voiture (`282 368 302 157`) ou le ballon (`976 306 183 294`). Le débordement est masqué pour exclure les autres éléments du concept. Les mesures et commandes restent celles de l’application ; aucun chiffre de la maquette n’est utilisé comme mesure.

Les contours, la perspective, le câble bleu, le thermomètre, les tuyaux et les ombres proviennent de la même source. L’image est incluse dans le conteneur et servie localement, sans service externe. La netteté maximale dépend de la résolution de l’image originale.

Vérifications locales : empreintes identiques de la source et de sa copie ; 11 tests frontend réussis ; construction TypeScript/Vite avec l’image embarquée ; 3 parcours navigateur réussis, incluant les neuf largeurs et le stress de police. Captures ordinateur et téléphone inspectées. Aucun changement au pilotage énergétique ni aux accès des connecteurs ; aucune commande réelle effectuée.

L’image Docker 0.1.3 et le Compose permettent la mise à jour en conservant le même volume de données.

Publication privée réussie : [workflow Linux et Docker](https://github.com/Macorou/solar-energy-manager/actions/runs/40463554465), commit `ebec32a8d00a14f535fb3c5425c63b72a1cf2dc8`, digest `sha256:6541744e1ea6bd9761efb0187e4306b349b7d34e852d1f2e87a221ab4cb97af8`. Le téléchargement authentifié, le refus anonyme et la provenance ont été vérifiés.
