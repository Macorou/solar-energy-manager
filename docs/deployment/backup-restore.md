# Sauvegarde, mise à jour et restauration

Sauvegarder **tout le volume `/data`**, notamment `app.db` et `secrets/master.key`. La base seule ne permet pas de retrouver les accès chiffrés. Une copie de clé doit être protégée comme les mots de passe de l’installation.

Procédure simple avec Portainer : mettre les appareils en pause et vérifier l’arrêt observé, arrêter le conteneur proprement, sauvegarder le volume complet avec votre outil de sauvegarde habituel, puis redémarrer. La base SQLite et sa clé sont ainsi cohérentes. Éviter une copie à chaud du seul fichier SQLite. Le code dispose aussi d’une sauvegarde SQLite par l’API native `backup()` pour l’outillage d’administration.

Avant chaque mise à jour, conserver une sauvegarde et le digest de l’image actuelle. Changer `SEM_VERSION` vers une version explicitement publiée, puis recréer la Stack en conservant son volume. Contrôler les connexions, les mesures et le journal au redémarrage. Une commande incertaine reste signalée et n’est pas rejouée comme un nouveau démarrage.

Pour restaurer, arrêter le conteneur, rétablir le volume entier avec sa clé et les droits UID/GID 10001, puis relancer l’image correspondant à cette sauvegarde. Ne pas régénérer la clé si elle manque. Le logiciel refuse une base existante sans clé. La V1 utilise le schéma SQLite version 1 ; une ancienne image ne doit pas être supposée compatible avec une future migration.

Ne jamais supprimer le volume en recréant la Stack. Ne jamais lancer simultanément un ancien et un nouveau conteneur sur le même volume. Les secrets ne figurent pas dans le Compose ou dans les sorties de diagnostic de l’application.
