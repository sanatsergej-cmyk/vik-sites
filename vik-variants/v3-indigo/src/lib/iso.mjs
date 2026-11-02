// Изометрическая проекция для SVG-сцен V3.
// Мир: x — вправо-вниз, y — влево-вниз, z — вверх. Видимые грани коробки: верх (z=max), левая (y=max), правая (x=max).

const COS = Math.cos(Math.PI / 6);
const SIN = 0.5;
const r1 = (n) => Math.round(n * 10) / 10;

export function makeIso(S = 40) {
  const p = (x, y, z = 0) => [r1((x - y) * COS * S), r1((x + y) * SIN * S - z * S)];
  const pts = (arr) => arr.map((a) => p(...a).join(',')).join(' ');
  const path = (arr) => 'M' + arr.map((a) => p(...a).join(' ')).join(' L');

  const box = (x, y, z, w, d, h) => {
    const x1 = x + w, y1 = y + d, z1 = z + h;
    return {
      top: pts([[x, y, z1], [x1, y, z1], [x1, y1, z1], [x, y1, z1]]),
      left: pts([[x, y1, z], [x1, y1, z], [x1, y1, z1], [x, y1, z1]]),
      right: pts([[x1, y, z], [x1, y1, z], [x1, y1, z1], [x1, y, z1]]),
      // Видимый контур (для «рисования» линией): нижние рёбра передних граней + вертикали + верх.
      edges: path([[x, y1, z], [x1, y1, z], [x1, y, z], [x1, y, z1], [x, y, z1], [x, y1, z1], [x, y1, z]]) +
        ' ' + path([[x, y1, z1], [x1, y1, z1], [x1, y, z1]]) + ' ' + path([[x1, y1, z1], [x1, y1, z]]),
    };
  };

  // Окружность в горизонтальной плоскости -> эллипс, оси параллельны экрану.
  const ell = (x, y, z, r) => {
    const [cx, cy] = p(x, y, z);
    return { cx, cy, rx: r1(1.2247 * r * S), ry: r1(0.7071 * r * S) };
  };

  // Сечение трубы на плоскости x=const (правая грань) или y=const (левая грань).
  const section = (axis, x, y, z, r, n = 20) => {
    const out = [];
    for (let i = 0; i < n; i++) {
      const t = (i / n) * Math.PI * 2;
      const a = Math.cos(t) * r, b = Math.sin(t) * r;
      out.push(axis === 'x' ? [x, y + a, z + b] : [x + a, y, z + b]);
    }
    return pts(out);
  };

  // Вертикальный цилиндр (колодец, стояк): боковые образующие + верхний эллипс.
  const cyl = (x, y, z0, z1, r) => {
    const top = ell(x, y, z1, r), bot = ell(x, y, z0, r);
    return {
      top,
      sides: `M${top.cx - top.rx} ${top.cy} L${bot.cx - bot.rx} ${bot.cy} A${bot.rx} ${bot.ry} 0 0 0 ${bot.cx + bot.rx} ${bot.cy} L${top.cx + top.rx} ${top.cy}`,
    };
  };

  // Прямоугольник на вертикальной плоскости y=const или x=const (окна, щиты).
  const rectY = (y, x0, z0, w, h) => pts([[x0, y, z0], [x0 + w, y, z0], [x0 + w, y, z0 + h], [x0, y, z0 + h]]);
  const rectX = (x, y0, z0, d, h) => pts([[x, y0, z0], [x, y0 + d, z0], [x, y0 + d, z0 + h], [x, y0, z0 + h]]);

  return { S, p, pts, path, box, ell, section, cyl, rectY, rectX };
}

// Цвета систем (функциональная маркировка, приглушённые тона под тёмный индиго).
export const SYS = {
  vodosnabzhenie: { c: 'var(--sys-water)', k: 'water' },
  kanalizatsiya: { c: 'var(--sys-sewer)', k: 'sewer' },
  teplosnabzhenie: { c: 'var(--sys-heat)', k: 'heat' },
  elektrosnabzhenie: { c: 'var(--sys-elec)', k: 'elec' },
  ventilyatsiya: { c: 'var(--sys-vent)', k: 'vent' },
  gazosnabzhenie: { c: 'var(--sys-gas)', k: 'gas' },
};
