import matplotlib.pyplot as plt
import numpy as np
import os

# Set Korean font
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# Generate dummy data
days = np.arange(1, 31)
ma20 = np.full_like(days, 10000, dtype=float)
# Stock price starts near 10000, then shoots up
price = 10000 + 500 * np.sin(days * 0.5)
price[-5:] = [10500, 11000, 11500, 12000, 12500]  # Shoot up to 125%

fig, ax = plt.subplots(figsize=(10, 6))

# Plot lines
ax.plot(days, ma20, label='20일 이동평균선 (10,000원 기준)', color='blue', linewidth=2, linestyle='--')
ax.plot(days, price, label='실제 주가 (현재가)', color='black', linewidth=3)

# Safe zone (<= 120%)
ax.fill_between(days, ma20, ma20 * 1.2, color='green', alpha=0.1, label='이격도 120% 이하 (안전 진입 구간)')

# Danger zone (> 120%)
ax.fill_between(days, ma20 * 1.2, 13000, color='red', alpha=0.1, label='이격도 120% 초과 (과열/위험 구간)')

# Annotate 120% line
ax.axhline(y=12000, color='red', linestyle=':', linewidth=2)
ax.text(2, 12100, '마지노선: 이격도 120% (주가 12,000원)', color='red', fontsize=12, fontweight='bold')

# Annotate disparity gap
ax.annotate('', xy=(29, 12000), xytext=(29, 10000),
            arrowprops=dict(arrowstyle='<->', color='purple', lw=2))
ax.text(25.5, 11000, '+20% 차이\n(= 이격도 120%)', color='purple', fontsize=12, fontweight='bold')

ax.set_title('20일 이동평균선 이격도 120%의 의미', fontsize=16, fontweight='bold', pad=20)
ax.set_xlabel('시간 (일)', fontsize=12)
ax.set_ylabel('주가 (원)', fontsize=12)
ax.set_ylim(9000, 13000)
ax.legend(loc='upper left', fontsize=11)
ax.grid(True, alpha=0.3)

plt.tight_layout()
save_path = r'C:\Users\Hubnet\.gemini\antigravity-ide\brain\d99d2ece-197c-4ebe-b596-d86a4a53a42d\disparity_chart.png'
plt.savefig(save_path, dpi=150)
print(f"Saved to {save_path}")
