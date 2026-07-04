# E2 frame — parametric CAD

`e2_frame.scad` — параметрична друкована рама 5″ авто-тарана E2. Числа дзеркалять
[`cuas/design/e2_config.py`](../cuas/design/e2_config.py); ТТХ: `python -m cuas.design.report`.

## Рендер (OpenSCAD, безкоштовний)
```
mkdir -p cad/out
openscad -D 'part="frame"'        -o cad/out/e2_frame.stl        cad/e2_frame.scad
openscad -D 'part="battery_tray"' -o cad/out/e2_battery_tray.stl cad/e2_frame.scad
openscad -D 'part="nose"'         -o cad/out/e2_nose.stl         cad/e2_frame.scad
```
`out/` — згенеровані STL/PNG (у .gitignore).

## Деталі
- **frame** — цілісно: X-промені + хаб (ванна стека 30.5) + ніс (з отвором під камеру).
- **battery_tray** — ложе 6S 1300 зі стрічковими прорізами (окремий друк).
- **nose** — той самий ніс standalone (на випадок ремонту/ітерації).

Друк і збірка: [`../cuas/design/ASSEMBLY.md`](../cuas/design/ASSEMBLY.md).
Щоб змінити геометрію (розмах, товщину променя, довжину носа) — правте параметри вгорі `e2_frame.scad` або конфіг і перерендерюйте.
