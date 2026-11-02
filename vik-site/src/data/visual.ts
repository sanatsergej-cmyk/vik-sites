// Оформление V1 «Золото»: визуальные акценты направлений. Только вёрстка, без текстов и фактов.
// hue — оттенок золота в формате "R G B" для rgb(var(--hue) / a).
// art — ИИ-иллюстрация из визуальных концепций 09.10 (не фото объекта, подпись «Иллюстрация»).
// photo — id реального фото из content/photos.mjs (показывается только при PUBLIC_PHOTOS=1).

export type DirVisual = { hue: string; tone: string; art?: string; artAlt?: string; artW?: number; artH?: number; photo?: string };

export const dirVisual: Record<string, DirVisual> = {
  vodosnabzhenie: { hue: '226 216 190', tone: 'белое золото', photo: 'water-node' },
  teplosnabzhenie: { hue: '226 146 92', tone: 'красное золото', photo: 'itp-1' },
  elektrosnabzhenie: { hue: '243 205 96', tone: 'жёлтое золото', photo: 'shchitovaya' },
  ventilyatsiya: { hue: '200 194 122', tone: 'зелёное золото', photo: 'ventkamera' },
  gazosnabzhenie: { hue: '234 166 70', tone: 'янтарное золото', photo: 'gas-facade' },
};

export const photosOn = import.meta.env.PUBLIC_PHOTOS === '1';
export const artLabel = 'Иллюстрация';

// Выноски на изометрических рендерах (public/gen/iso-*.jpg, 1920×1072). Только вёрстка:
// x, y — положение точки в процентах картинки (проверено скриншотами 390/800/1440);
// ref — откуда берётся подпись: ['scope', группа, пункт] из d.scopeGroups или ['step', i] из d.steps;
// side — с какой стороны от точки подпись на широком экране: r | l | u | d.
export type IsoRef = ['scope', number, number] | ['step', number];
export type IsoPin = { x: number; y: number; ref: IsoRef; side: 'r' | 'l' | 'u' | 'd' };

export const isoPins: Record<string, IsoPin[]> = {
  vodosnabzhenie: [
    { x: 15.6, y: 74.6, ref: ['scope', 0, 0], side: 'u' },
    { x: 39.6, y: 50, ref: ['scope', 0, 3], side: 'u' },
    { x: 65.6, y: 17.2, ref: ['scope', 1, 0], side: 'l' },
  ],
  teplosnabzhenie: [
    { x: 13, y: 46, ref: ['scope', 0, 2], side: 'r' },
    { x: 39.6, y: 71, ref: ['scope', 0, 0], side: 'd' },
    { x: 58.5, y: 59.5, ref: ['scope', 0, 1], side: 'r' },
    { x: 68.3, y: 41, ref: ['scope', 1, 0], side: 'l' },
    { x: 90.2, y: 25.3, ref: ['scope', 1, 1], side: 'l' },
  ],
  elektrosnabzhenie: [
    { x: 24.5, y: 35, ref: ['scope', 0, 1], side: 'u' },
    { x: 45, y: 70, ref: ['scope', 0, 0], side: 'd' },
    { x: 62.5, y: 47, ref: ['scope', 1, 1], side: 'r' },
    { x: 80.5, y: 33, ref: ['scope', 1, 0], side: 'u' },
  ],
  ventilyatsiya: [
    { x: 61, y: 13.5, ref: ['scope', 0, 1], side: 'r' },
    { x: 38, y: 30.5, ref: ['scope', 0, 0], side: 'l' },
    { x: 52, y: 85, ref: ['scope', 0, 3], side: 'l' },
    { x: 66, y: 80, ref: ['scope', 0, 2], side: 'r' },
  ],
  gazosnabzhenie: [
    { x: 34.6, y: 53.5, ref: ['step', 1], side: 'u' },
    { x: 50, y: 67, ref: ['scope', 0, 0], side: 'd' },
    { x: 61.5, y: 36, ref: ['step', 4], side: 'r' },
  ],
};

// Главная, «СМР по системам»: точки систем на iso-kompleks (здание со всеми сетями в разрезе).
export const kompleksPins: Record<string, { x: number; y: number; side: 'r' | 'l' | 'u' | 'd' }> = {
  vodosnabzhenie: { x: 29.2, y: 65.3, side: 'l' },
  teplosnabzhenie: { x: 41.7, y: 67.8, side: 'd' },
  elektrosnabzhenie: { x: 59.1, y: 50.8, side: 'r' },
  ventilyatsiya: { x: 52, y: 10, side: 'r' },
  gazosnabzhenie: { x: 60, y: 69.5, side: 'r' },
};
