# Illustrations transparentes des appareils

Fichiers utilisés par l’interface :

- `frontend/src/assets/car-transparent.png` : 1774 × 887 pixels, RGBA.
- `frontend/src/assets/tank-transparent.png` : 1024 × 1536 pixels, RGBA.

Les deux illustrations ont été détourées à partir des dessins de
`frontend/src/assets/pilotage-concept-original.png` avec l’outil intégré
`image_gen`, en demandant une transparence réelle. Aucun traitement Python
de modification d’image n’a été appliqué. L’original est conservé comme référence.

Une première extraction a isolé chaque objet de la maquette. Les instructions
finales de nettoyage étaient les suivantes.

## Voiture

> Edit only the alpha/background extraction of this car asset. Keep the
> illustrated car itself exactly the same: white opaque body panels, fine dark
> outlines, wheels, windows, blue plug and cable, original orientation and
> proportions. Remove ALL ground shadow, white floor/oval underneath, jagged
> white background remnants and fringe noise outside the car and cable. Every
> pixel outside the vehicle and blue cable must be fully transparent; no halo,
> glow, floor, rectangle, backdrop or checkerboard. Clean antialiased cutout
> edges suitable for a dark navy dashboard. Do not redraw or recolor the car.
> Tightly framed landscape transparent PNG.

## Ballon

> Edit only the exterior alpha/background extraction of this hot-water tank
> asset. Keep the white tank body itself exactly the same, fully opaque,
> including its blue-gray outline, thermometer and two lower pipe connections.
> Completely remove the external white/gray glow or fog around the tank, and
> remove the oval ground shadow below its pipes. Every pixel outside the tank
> silhouette and its pipes must be fully transparent; no glow, halo, floor,
> oval, backdrop, rectangle or checkerboard. Clean antialiased cutout edges
> suitable for a dark navy dashboard. Do not redraw, recolor or change the tank.
> Tightly framed portrait transparent PNG.

La présence du canal alpha et des coins entièrement transparents a été vérifiée
dans les fichiers et dans les ressources réellement chargées par le navigateur.
Le rendu a été contrôlé sur les deux thèmes, en affichage ordinateur et mobile.
