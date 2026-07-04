import numpy as np


def drone_score(x: np.ndarray, sr: int) -> float:
    """0..1: наскільки сигнал схожий на гребінь рівновіддалених гармонік (BPF дрона 60-180 Гц).

    Оцінка = найкраще (за f0) відношення середньої магнітуди на 7 гармоніках до
    середньої магнітуди всієї смуги. Гребінь концентрує енергію -> велике відношення;
    білий шум розмазаний -> відношення ~1. Стійкіше за нормований HPS, який
    завищував шум через максимум по багатьох кандидатах f0."""
    x = x - x.mean()
    n = 1 << int(np.ceil(np.log2(len(x))))
    X = np.abs(np.fft.rfft(x, n))
    f = np.fft.rfftfreq(n, 1 / sr)
    band = (f >= 40) & (f <= 2000)
    Xb = X[band]
    fb = f[band]
    if Xb.max() <= 0:
        return 0.0
    band_mean = float(np.mean(Xb)) + 1e-9
    best = 0.0
    for f0 in range(60, 181, 2):
        idx = [np.argmin(np.abs(fb - f0 * k)) for k in range(1, 8)]
        harmonic_mean = float(np.mean(Xb[idx]))
        best = max(best, harmonic_mean / band_mean)
    # best ~1 для шуму, >>1 для гребеня; лінійно мапимо надлишок над 1.
    return float(np.clip((best - 1.0) / 6.0, 0, 1))
