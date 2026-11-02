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
