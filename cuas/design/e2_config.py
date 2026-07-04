"""Єдине джерело параметрів E2 (5" друкований авто-таран, 6S). Одиниці в іменах."""

# Компоненти: маса + позиція (x уздовж осі ніс(+)<->хвіст, y право, z верх), мм від центру рами
COMPONENTS = [
    {"name": "motor_fr", "mass_g": 32, "x_mm": 78, "y_mm": 78, "z_mm": 8},
    {"name": "motor_fl", "mass_g": 32, "x_mm": 78, "y_mm": -78, "z_mm": 8},
    {"name": "motor_rr", "mass_g": 32, "x_mm": -78, "y_mm": 78, "z_mm": 8},
    {"name": "motor_rl", "mass_g": 32, "x_mm": -78, "y_mm": -78, "z_mm": 8},
    {"name": "props", "mass_g": 20, "x_mm": 0, "y_mm": 0, "z_mm": 12},
    {"name": "esc_4in1", "mass_g": 30, "x_mm": 0, "y_mm": 0, "z_mm": 0},
    {"name": "fc", "mass_g": 8, "x_mm": 0, "y_mm": 0, "z_mm": 6},
    {"name": "rx", "mass_g": 3, "x_mm": -20, "y_mm": 0, "z_mm": 10},
    {"name": "battery_6s_1300", "mass_g": 205, "x_mm": -10, "y_mm": 0, "z_mm": 18},
    {"name": "compute_pi_cam", "mass_g": 30, "x_mm": 90, "y_mm": 0, "z_mm": 4},
    {"name": "payload_inert", "mass_g": 180, "x_mm": 20, "y_mm": 0, "z_mm": 0},
    {"name": "frame_petg", "mass_g": 140, "x_mm": 0, "y_mm": 0, "z_mm": 4},
    {"name": "misc", "mass_g": 30, "x_mm": 0, "y_mm": 0, "z_mm": 6},
]

# Пропульсія
MOTOR_KV = 1960
V_BATT_NOMINAL = 22.2       # 6S nominal
V_BATT_FULL = 25.2          # 6S charged
PROP_DIAM_IN = 5.0
PROP_PITCH_IN = 4.3
PROP_BLADES = 3
THRUST_PER_MOTOR_G = 1350   # 2207/1960KV, 5x4.3x3, 6S (datasheet ballpark, max)
ETA_RPM = 0.65             # частка KV*V, якої досягає навантажений мотор
LEVEL_FACTOR = 0.8         # частка pitch-швидкості в реальному горизонт. польоті (розвантаження пропа)
EST_AVG_POWER_W = 400.0    # оцінка середньої потужності в агресивному польоті

# Аеродинаміка (ефективний CdA квадра у нахиленому польоті)
CD_BODY = 1.0
FRONTAL_AREA_M2 = 0.012

# Акумулятор
BATT_CAP_AH = 1.3
BATT_DOD = 0.85
BATT_ETA = 0.85

# Геометрія рами (5" true-X)
WHEELBASE_MM = 220.0       # діагональ мотор-мотор
MOTOR_MOUNT_MM = 16.0      # монтаж мотора (16x16 M3, для 2207)
STACK_MOUNT_MM = 30.5      # монтаж стека (30.5x30.5 M3)

# Рама/промінь (PETG) — для резонансної перевірки
ARM_W_MM = 7.0             # ширина променя
ARM_H_MM = 9.0             # висота (глибока секція)
ARM_LEN_MM = 110.0         # від центру до мотора (WHEELBASE/2)
E_PETG_PA = 1.8e9          # модуль Юнга друкованого PETG (консервативно)
RHO_PETG = 1270.0          # густина PETG, кг/м^3
MOTOR_MASS_G = 32          # маса на кінці променя (мотор)
