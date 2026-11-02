// Фото для сайта. Источник: снимки, присланные Виталием (его объявления на Авито, 17.09.2026).
// verified:false — принадлежность объектов и право публикации не подтверждены, поэтому подписи нейтральные
// («фото инженерных систем»), без слов «наш объект». Показываются при PUBLIC_PHOTOS=1 (закрытый стенд).
export const photos = [
  { id: 'itp-1', src: '/photos/itp-1.jpg', dir: 'teplosnabzhenie', alt: 'Тепловой пункт: теплообменники, насосы, расширительный бак', cap: 'Тепловой пункт' },
  { id: 'itp-2', src: '/photos/itp-2.jpg', dir: 'teplosnabzhenie', alt: 'Помещение теплового пункта с обвязкой и приборами учёта', cap: 'Обвязка и узлы учёта' },
  { id: 'teplotrassa-kamera', src: '/photos/teplotrassa-kamera.jpg', dir: 'teplosnabzhenie', alt: 'Теплотрасса в изоляции в железобетонной камере', cap: 'Теплотрасса и камера' },
  { id: 'ventkamera', src: '/photos/ventkamera.jpg', dir: 'ventilyatsiya', alt: 'Венткамера с приточными установками и трубопроводами', cap: 'Венткамера' },
  { id: 'elektromontazh', src: '/photos/elektromontazh.jpg', dir: 'elektrosnabzhenie', alt: 'Электрооборудование и кабельные линии на монтаже', cap: 'Электромонтаж' },
  { id: 'shchitovaya', src: '/photos/shchitovaya.jpg', dir: 'elektrosnabzhenie', alt: 'Щитовая: шкафы управления и распределения', cap: 'Щитовая' },
  // ИИ-иллюстрации (Polza, Nano Banana, 01.11.2026) — не фото объектов, подпись начинается с «Иллюстрация».
  { id: 'water-node', src: '/photos/water-node.jpg', dir: 'vodosnabzhenie', ai: true, alt: 'Иллюстрация: водомерный узел с задвижками в техническом помещении', cap: 'Иллюстрация: водомерный узел' },
  { id: 'water-trench', src: '/photos/water-trench.jpg', dir: 'vodosnabzhenie', ai: true, alt: 'Иллюстрация: прокладка наружного водопровода из полиэтиленовых труб в траншее', cap: 'Иллюстрация: наружный водопровод' },
  { id: 'gas-facade', src: '/photos/gas-facade.jpg', dir: 'gazosnabzhenie', ai: true, alt: 'Иллюстрация: надземный газопровод на фасаде складского здания', cap: 'Иллюстрация: газопровод на фасаде' },
  { id: 'gas-trench', src: '/photos/gas-trench.jpg', dir: 'gazosnabzhenie', ai: true, alt: 'Иллюстрация: укладка полиэтиленового газопровода в траншею', cap: 'Иллюстрация: подземный газопровод' },
  { id: 'heat-trench', src: '/photos/heat-trench.jpg', dir: 'teplosnabzhenie', ai: true, alt: 'Иллюстрация: сварка труб в ППУ-изоляции при строительстве теплосети', cap: 'Иллюстрация: строительство теплосети' },
];
export const photosNote = 'Фото и иллюстрации инженерных систем. Принадлежность объектов на фото уточняется перед публикацией; изображения с подписью «Иллюстрация» созданы для сайта.';
