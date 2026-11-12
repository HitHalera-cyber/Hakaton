extends Node
## Interface languages. English strings in the code are the keys; this file
## holds their translations and registers them with Godot's TranslationServer.
## Labels and buttons translate their text automatically; composed strings in
## code go through tr() / TranslationServer.translate().
## To add a language: add a dictionary to TABLES and a name to NAMES.

const NAMES := {"en": "English", "ru": "Русский"}

const RU := {
	# main menu
	"PLAY": "ИГРАТЬ", "LOCAL MULTIPLAYER": "ИГРА ВДВОЁМ", "GARAGE": "ГАРАЖ", "TRACKS": "ТРАССЫ",
	"RECORDS": "РЕКОРДЫ", "SETTINGS": "НАСТРОЙКИ", "QUIT": "ВЫХОД",
	"SMALL CARS. BIG DRIFT.": "МАЛЕНЬКИЕ МАШИНЫ. БОЛЬШОЙ ДРИФТ.",
	"Enter / A — select     Esc / Start — pause in race     v0.1": "Enter / A — выбор     Esc / Start — пауза в гонке     v0.1",
	"Achievement: ": "Достижение: ",
	# race setup
	"RACE SETUP": "НАСТРОЙКА ЗАЕЗДА", "PLAYERS": "ИГРОКИ", "MODE": "РЕЖИМ", "TRACK": "ТРАССА", "LAPS": "КРУГИ",
	"2P SCREEN": "ЭКРАН 2P", "1P CAR": "МАШИНА 1P", "2P CAR": "МАШИНА 2P", "START RACE": "СТАРТ", "BACK": "НАЗАД",
	"1 Player": "1 игрок", "2 Players": "2 игрока", "Split screen": "Разделённый", "Shared camera": "Общая камера",
	"Championship: all %d tracks": "Чемпионат: все %d трассы",
	"Best race (3 laps): %s": "Лучший заезд (3 круга): %s", "Best lap: %s": "Лучший круг: %s",
	"Best drift score: %s": "Рекорд дрифта: %s", "Surface: %s    Target lap: %s": "Покрытие: %s    Цель на круг: %s",
	"Asphalt": "Асфальт", "Wet": "Мокрый асфальт", "Dirt": "Грунт", "Snow": "Снег",
	# modes
	"Time Attack": "На время", "Drift Attack": "Дрифт-атака", "Practice": "Тренировка", "Championship": "Чемпионат",
	"Ghost Race": "Гонка с призраком", "Local Versus": "Дуэль", "Local Co-op": "Кооператив",
	"Beat the clock. Fastest total time wins.": "Гонка с секундомером: побеждает лучшее общее время.",
	"Score as many drift points as you can before the last lap ends.": "Наберите как можно больше очков дрифта до конца последнего круга.",
	"Free driving. No finish line, lap times are still shown.": "Свободная езда без финиша, время кругов всё равно считается.",
	"All four tracks against CPU rivals. Points for places and style.": "Все четыре трассы против компьютерных соперников. Очки за места.",
	"Race against the replay of your best lap.": "Заезд против записи вашего лучшего круга.",
	"Head to head: first over the line wins, drift points break ties.": "Один на один: побеждает тот, кто первым финиширует.",
	"Team drift score. Drift side by side for the tandem bonus.": "Общий счёт команды. Дрифт рядом друг с другом даёт бонус тандема.",
	# tracks
	"Serpentine, sunset, cliffs": "Серпантин, закат, обрывы", "Rain, neon, reflections": "Дождь, неон, отражения",
	"Dirt, trees, tight turns": "Грунт, деревья, узкие повороты", "Snow, ice, tricky corners": "Снег, лёд, коварные повороты",
	"Toy track across a desk": "Игрушечная трасса по письменному столу", "Downtown at night, rain": "Ночной центр города под дождём",
	"Light lines in a digital void": "Линии света в цифровой пустоте", "Autumn forest, creek, sunset": "Осенний лес, ручей, закат",
	"Plastic": "Пластик", "Gymkhana": "Джимхана", "Tandem Chase": "Тандем-погоня", "Training": "Обучение",
	"90 seconds on an open lot: donuts around the posts, figure eights, ramps and boost pads.": "90 секунд на открытой площадке: пончики вокруг столбов, восьмёрки, трамплины и ускорители.",
	"One leads, one chases: the chaser scores for drifting close behind. Roles swap every lap.": "Один ведёт, второй догоняет: преследователь получает очки за дрифт вплотную. Каждый круг роли меняются.",
	"Step-by-step lessons: throttle, steering, handbrake drift, boost and donuts.": "Пошаговые уроки: газ, руль, дрифт на ручнике, ускорение и пончики.",
	"AIR": "ПОЛЁТ", "DONUT": "ПОНЧИК", "FIGURE EIGHT!": "ВОСЬМЁРКА!", "TIME %d   DONUTS %d   EIGHTS %d": "ВРЕМЯ %d   ПОНЧИКИ %d   ВОСЬМЁРКИ %d",
	"TRAINING": "ОБУЧЕНИЕ", "ROUND %d — YOU LEAD": "РАУНД %d — ВЫ ВЕДЁТЕ", "ROUND %d — CHASE! %d px": "РАУНД %d — ДОГОНЯЙТЕ! %d px",
	"ROLES SWAP!": "СМЕНА РОЛЕЙ!", "GOOD!": "ОТЛИЧНО!", "STEP": "ШАГ",
	"Training complete! Press Esc to leave or keep practising.": "Обучение пройдено! Esc — выйти, или тренируйтесь дальше.",
	"Hold THROTTLE (W / Up / RT) and reach 100 km/h": "Держите ГАЗ (W / Вверх / RT) и разгонитесь до 100 км/ч",
	"Steer (A-D / Left-Right / stick) and drive one full circle": "Рулите (A-D / Влево-Вправо / стик) и проедьте полный круг",
	"BRAKE (S / Down / LT) and stop the car": "ТОРМОЗ (S / Вниз / LT) — остановите машину",
	"Hold the HANDBRAKE (Shift / Space / X) while turning to start a drift": "Зажмите РУЧНИК (Shift / Пробел / X) в повороте — начнётся занос",
	"Keep the slide for 2 seconds: steer into the drift, stay on the throttle": "Удержите занос 2 секунды: руль в сторону заноса, газ не отпускайте",
	"Charge the BOOST to orange (2 cells) in a drift, then straighten up": "Зарядите УСКОРЕНИЕ до оранжевого (2 деления) и выпрямитесь",
	"Drift a full DONUT around one of the orange posts": "Сделайте ПОНЧИК — полный круг в заносе вокруг оранжевого столба",
	"BOOST PAD": "УСКОРИТЕЛЬ", "DRIFT ONLY": "ТОЛЬКО В ЗАНОСЕ", "NIGHT FALLS": "НАСТУПАЕТ НОЧЬ", "SUNRISE": "РАССВЕТ", "RAIN — LESS GRIP!": "ДОЖДЬ — СЦЕПЛЕНИЕ НИЖЕ!",
	"THE RAIN STOPS": "ДОЖДЬ ЗАКОНЧИЛСЯ", "Changing weather and time of day": "Смена погоды и времени суток", "Cup %d": "Кубок %d", "DIRECTION": "НАПРАВЛЕНИЕ", "Normal": "Обычное", "Reverse": "Обратное",
	"Tight hairpins under cherry blossom": "Крутые шпильки под цветущей сакурой", "Fast sweepers between towers": "Быстрые дуги между высотками",
	"Dirt switchbacks through the pines": "Грунтовые серпантины среди сосен", "Long icy sweepers and a frozen lake": "Длинные ледяные дуги и замёрзшее озеро",
	# garage
	"TUNING": "ТЮНИНГ", "PAINT": "ПОКРАСКА", "RIMS": "ДИСКИ", "DECAL": "НАКЛЕЙКА",
	"ENGINE": "ДВИГАТЕЛЬ", "TYRES": "ШИНЫ", "SUSPENSION": "ПОДВЕСКА", "BRAKES": "ТОРМОЗА",
	"Acceleration and top speed": "Разгон и максимальная скорость", "Grip and steering": "Сцепление и управляемость",
	"Drift control and stability": "Контроль заноса", "Braking power": "Сила торможения",
	"locked": "закрыто", "MAX": "МАКС", "upgrade %d CR": "улучшить %d CR", "(LOCKED)": "(ЗАКРЫТА)",
	"USE FOR 1P": "ВЗЯТЬ ДЛЯ 1P", "USE FOR 2P": "ВЗЯТЬ ДЛЯ 2P", "UNLOCK %d CR": "КУПИТЬ %d CR",
	"Not enough credits — race to earn more.": "Не хватает кредитов — заработайте их в гонках.",
	"%s upgraded to level %d": "%s: уровень %d", "Need %d CR to unlock.": "Нужно %d CR.", "%s unlocked!": "%s теперь ваша!",
	"%dP drives the %s": "%dP едет на %s",
	"Steel": "Сталь", "Mesh": "Сетка", "Spoke": "Спицы", "Gold": "Золото",
	"None": "Нет", "Stripes": "Полосы", "Flame": "Пламя", "Number": "Номер", "Checker": "Шахматка", "Bolt": "Молния",
	"Speed": "Скорость", "Accel": "Разгон", "Grip": "Сцепление", "Drift": "Дрифт",
	"Honest city hatchback. Forgiving and easy to slide.": "Простой городской хэтчбек. Прощает ошибки, легко заносится.",
	"Rear-drive coupe made for long, technical drifts.": "Заднеприводное купе для длинных техничных заносов.",
	"Low, light and fast. Grips hard, slides sharp.": "Низкая, лёгкая и быстрая. Держит дорогу, срывается резко.",
	"Tiny rounded classic. Slow, but rotates like a top.": "Крошечная классика. Небыстрая, но крутится как волчок.",
	"All-wheel drive. Keeps its grip on dirt and snow.": "Полный привод. Держит дорогу на грунте и снегу.",
	"Wide-body project car. Upgrades give it more.": "Широкий проект-кар. Улучшения дают ему больше.",
	# records
	"MODE ": "РЕЖИМ ", "BEST RACE": "ЛУЧШИЙ ЗАЕЗД", "BEST LAP": "ЛУЧШИЙ КРУГ", "BEST DRIFT": "ЛУЧШИЙ ДРИФТ",
	"BEST COMBO": "ЛУЧШЕЕ КОМБО", "ACHIEVEMENTS": "ДОСТИЖЕНИЯ", "CAREER": "КАРЬЕРА",
	"No records yet — go and set some!": "Рекордов пока нет — самое время их поставить!",
	"Races: %d    Drift points: %s    Best combo: %s    Distance: %.1f km": "Заездов: %d    Очки дрифта: %s    Лучшее комбо: %s    Пробег: %.1f км",
	"RESET PROGRESS": "СБРОСИТЬ ПРОГРЕСС", "PRESS AGAIN TO CONFIRM": "НАЖМИТЕ ЕЩЁ РАЗ",
	" (%s laps)": " (%s кр.)",
	"First Slide — bank your first drift": "Первый занос — заработайте очки за дрифт",
	"Combo Artist — 3 000 points in one combo": "Мастер комбо — 3 000 очков за одно комбо",
	"Smoke Machine — 10 000 points in one combo": "Дымовая машина — 10 000 очков за одно комбо",
	"Tourist — finish a race on every track": "Турист — финишируйте на каждой трассе",
	"Couch Crew — finish a two-player race": "Диванная команда — пройдите гонку вдвоём",
	"Champion — win a championship": "Чемпион — выиграйте чемпионат",
	"Collector — unlock every car": "Коллекционер — откройте все машины",
	"Ghost Buster — beat your own ghost": "Охотник за призраками — обгоните свой призрак",
	# settings
	"DISPLAY": "ЭКРАН", "AUDIO": "ЗВУК", "GAMEPLAY": "ИГРА", "GRAPHICS": "ГРАФИКА", "LANGUAGE": "ЯЗЫК",
	"Fullscreen": "Полный экран", "VSync": "Вертикальная синхронизация",
	"Pixel-perfect (integer) scaling": "Целочисленное масштабирование", "Show FPS": "Показывать FPS",
	"Master": "Общая", "Music": "Музыка", "Engine": "Двигатель", "Effects": "Эффекты",
	"GAMEPADS": "ГЕЙМПАДЫ", "Pad 1 > 1P, Pad 2 > 2P": "Пад 1 > 1P, пад 2 > 2P", "Keyboard 1P, Pad 1 > 2P": "1P клавиатура, пад 1 > 2P",
	"Camera shake": "Тряска камеры", "QUALITY": "КАЧЕСТВО", "Low": "Низкое", "Medium": "Среднее", "High": "Высокое",
	"STYLE": "СТИЛЬ", "Low quality turns off weather and glow and thins out smoke — for older PCs.":
		"Низкое качество отключает погоду и свечение и уменьшает дым — для слабых ПК.",
	"CONTROLS (keyboard) — select and press a key": "УПРАВЛЕНИЕ (клавиатура) — выберите и нажмите клавишу",
	"PLAYER %d": "ИГРОК %d", "Reset controls to default": "Сбросить управление",
	"Gamepads: RT/A gas · LT/B brake · stick steer · X/RB handbrake · Y reset": "Геймпад: RT/A газ · LT/B тормоз · стик руль · X/RB ручник · Y на трассу",
	"press a key...  (Esc cancels)": "нажмите клавишу...  (Esc — отмена)", "Press the new key for %s": "Нажмите новую клавишу: %s",
	"Cancelled": "Отменено", "Controls reset": "Управление сброшено",
	"Throttle": "Газ", "Brake / Reverse": "Тормоз / назад", "Steer left": "Руль влево", "Steer right": "Руль вправо",
	"Handbrake": "Ручник", "Back on track": "На трассу",
	# pause / results
	"PAUSED": "ПАУЗА", "Resume": "Продолжить", "Restart race": "Начать заново", "Quit to menu": "Выйти в меню",
	"P1: WASD + L-Shift   P2: Arrows + R-Shift   Reset: R / Backspace": "1P: WASD + L-Shift   2P: стрелки + R-Shift   На трассу: R / Backspace",
	"RESULTS": "РЕЗУЛЬТАТЫ", "%s WINS!": "ПОБЕДА: %s!", "FINISHED": "ФИНИШ", "DRIVER": "ПИЛОТ", "TIME": "ВРЕМЯ",
	"DRIFT": "ДРИФТ", "CHAMP": "ОЧКИ", "REWARD": "НАГРАДА", "DNF": "СХОД",
	"Next race": "Следующая гонка", "Race again": "Ещё раз", "Setup": "Настройка", "Garage": "Гараж", "Menu": "Меню",
	"TEAM %s — %s": "КОМАНДА %s — %s", "GOLD": "ЗОЛОТО", "SILVER": "СЕРЕБРО", "BRONZE": "БРОНЗА", "NO MEDAL": "БЕЗ МЕДАЛИ",
	"%d laps": "кругов: %d", "free run": "свободная езда",
	"%dP: new best race time!": "%dP: новый рекорд заезда!", "%dP: new best lap!": "%dP: новый рекорд круга!",
	"%dP: new drift record!": "%dP: новый рекорд дрифта!", "CHAMPIONSHIP STANDINGS:": "ИТОГИ ЧЕМПИОНАТА:",
	"%d. %s — %d pts": "%d. %s — %d очк.", "Champion bonus: +500 CR": "Бонус чемпиона: +500 CR",
	# HUD
	"BEST COMBO %s": "ЛУЧШЕЕ КОМБО %s", "COMBO %s": "КОМБО %s", "LAST %s": "ПОСЛ. %s", "   BEST %s": "   ЛУЧШ. %s",
	"LAP %d/%d": "КРУГ %d/%d", "LAP %d": "КРУГ %d", "FINAL LAP": "ПОСЛЕДНИЙ КРУГ", "   BEST!": "   РЕКОРД!",
	"KM/H": "КМ/Ч", "OFF ROAD": "ВНЕ ТРАССЫ", "ICE!": "ЛЁД!", "CLOSE!": "БЛИЗКО!", "TANDEM": "ТАНДЕМ",
	"WRONG WAY": "НЕ ТУДА", "FINISHED — waiting for others": "ФИНИШ — ждём остальных", "FINISH!": "ФИНИШ!",
	"GO!": "ВПЕРЁД!", "CATCH UP": "ДОГОНЯЕМ", "GHOST BEATEN!": "ПРИЗРАК ПОБЕЖДЁН!",
	"TEAM %s": "КОМАНДА %s", "GHOST %s": "ПРИЗРАК %s", "SET A LAP TO RACE YOUR GHOST": "ПРОЙДИТЕ КРУГ, ЧТОБЫ ПОЯВИЛСЯ ПРИЗРАК",
	"PRACTICE — ESC TO LEAVE": "ТРЕНИРОВКА — ESC ДЛЯ ВЫХОДА", "SCORE ATTACK": "НАБОР ОЧКОВ", "FINISH IN %d": "ФИНИШ ЧЕРЕЗ %d",
	"GREAT DRIFT": "ОТЛИЧНЫЙ ДРИФТ", "PERFECT DRIFT": "ИДЕАЛЬНЫЙ ДРИФТ", " CLEAN": " ЧИСТО", "CRASH": "АВАРИЯ",
	"SPIN OUT": "РАЗВОРОТ", "BOOST": "УСКОР.", "BOOST!": "УСКОРЕНИЕ!", "DRIFT ZONE": "ДРИФТ-ЗОНА", "ZONE %s": "ЗОНА %s",
	"Handbrake into corners to drift! Drifting charges a BOOST.": "Ручник в повороте — занос! Дрифт заряжает УСКОРЕНИЕ.", "1ST": "1-Й", "2ND": "2-Й", "3RD": "3-Й", "%dTH": "%d-Й",
	"Finish a gymkhana run": "Завершить заезд джимханы", "3 donuts in one run": "3 «пончика» за заезд", "A figure eight": "Восьмёрка",
	"Finish a race": "Финишировать в гонке", "Grade S in 5 drift zones in one race": "Оценка S в 5 дрифт-зонах за гонку",
	"A clean lap: no barrier touched": "Чистый круг без касаний отбойника", "NEW STAR: %s": "НОВАЯ ЗВЕЗДА: %s", "Stars %d/3": "Звёзды %d/3",
	"REPLAY": "ПОВТОР", "Best drift %s: %s · Enter — skip": "Лучший дрифт %s: %s · Enter — пропустить",
	"Gymkhana lot": "Площадка джимханы",
	"PHOTO MODE · Arrows / stick — move · Q / E — zoom · Enter / A — save photo · Esc — back": "ФОТОРЕЖИМ · Стрелки / стик — камера · Q / E — зум · Enter / A — снимок · Esc — назад",
	"Saved: %s": "Сохранено: %s", "Photo mode (F2)": "Фоторежим (F2)", "Best drift replay after the race": "Повтор лучшего дрифта после гонки",
	"DRAW": "НИЧЬЯ", "%dP WINS THE DUEL": "%dP ВЫИГРАЛ ДУЭЛЬ", "DUEL: %s (%s) · overall 1P %d : %d 2P": "ДУЭЛЬ: %s (%s) · всего 1P %d : %d 2P",
	"CUP DUEL: 1P %d pts — 2P %d pts · races won %d : %d": "ДУЭЛЬ КУБКА: 1P %d очк. — 2P %d очк. · гонок выиграно %d : %d",
	"THE DUEL IS A DRAW!": "ДУЭЛЬ ВНИЧЬЮ!", "%dP WINS THE CUP DUEL! (+300 CR)": "%dP ПОБЕДИЛ В ДУЭЛИ КУБКА! (+300 CR)",
	"2P DUEL — 1P VS 2P": "ДУЭЛЬ ВДВОЁМ — 1P ПРОТИВ 2P", "Wins: 1P %d : %d 2P    Draws: %d    Cup duels: 1P %d : %d 2P": "Победы: 1P %d : %d 2P    Ничьи: %d    Дуэли кубков: 1P %d : %d 2P",
	"Draw": "Ничья", "No duels yet — play a two-player race.": "Дуэлей пока нет — сыграйте гонку вдвоём.", "Challenge stars: %d / %d": "Звёзды испытаний: %d / %d",
	"Police Chase": "Полицейская погоня", "Hot Potato": "Бомба", "Elimination": "На выбывание",
	"Downtown: robbers grab cash and stay free for 2:30, cops box them in. Pick your side; bots take the rest.": "Город: грабители собирают деньги и 2:30 уходят от погони, полиция их зажимает. Выберите сторону — за остальных играют боты.",
	"Downtown: the bomb passes on contact. Get rid of it before the fuse runs out. Last car left wins.": "Город: бомба передаётся касанием. Избавьтесь от неё, пока не догорел фитиль. Побеждает последний уцелевший.",
	"Every 20 seconds the last car is knocked out. Be the last one standing.": "Каждые 20 секунд последняя машина выбывает. Останьтесь последним в игре.",
	"1P ROLE": "РОЛЬ 1P", "2P ROLE": "РОЛЬ 2P", "COPS": "ПОЛИЦЕЙСКИХ", "BOTS": "БОТЫ", "BOT LEVEL": "УРОВЕНЬ БОТОВ",
	"Robber": "Грабитель", "Cop": "Полицейский", "Rookie": "Новичок", "Pro": "Профи", "Ace": "Ас",
	"CASH": "ДЕНЬГИ", "BUSTED!": "АРЕСТ!", "%s BUSTED!": "%s АРЕСТОВАН!", "BUSTED — WAIT FOR THE OTHERS": "АРЕСТОВАН — ЖДИТЕ ОСТАЛЬНЫХ",
	"ESCAPE %s   BUST %d%%": "УХОДИ %s   АРЕСТ %d%%", "CATCH THEM %s   LEFT %d   %d m": "ЛОВИ %s   ОСТАЛОСЬ %d   %d м",
	"BUSTED! THE COPS WIN": "АРЕСТ! ПОБЕДА ПОЛИЦИИ", "THE ROBBERS GOT AWAY!": "ГРАБИТЕЛИ УШЛИ!",
	"%s HAS THE BOMB!": "БОМБА У %s!", "BOOM! %s IS OUT": "БУМ! %s ВЫБЫВАЕТ", "OUT — WAIT FOR THE OTHERS": "ВЫБЫЛ — ЖДИТЕ ОСТАЛЬНЫХ",
	"NEW BOMB SOON   ALIVE %d": "СКОРО НОВАЯ БОМБА   В ИГРЕ %d", "YOU HAVE THE BOMB! %d s — TOUCH SOMEONE": "БОМБА У ВАС! %d с — КОСНИТЕСЬ ДРУГОГО",
	"RUN! BOMB: %s %d s   ALIVE %d": "УДИРАЙ! БОМБА: %s %d с   В ИГРЕ %d", "%s SURVIVES!": "%s ВЫЖИЛ!",
	"%s IS OUT!": "%s ВЫБЫВАЕТ!", "NEXT OUT IN %d s   ALIVE %d": "ВЫБЫВАНИЕ ЧЕРЕЗ %d с   В ИГРЕ %d", "YOU ARE LAST!": "ВЫ ПОСЛЕДНИЙ!",
	"%s IS THE LAST ONE STANDING!": "%s — ПОСЛЕДНИЙ В ИГРЕ!", "OUT %s": "ВЫБЫЛ %s", "COP": "ПОЛИЦИЯ", "FREE": "НА СВОБОДЕ", "ALIVE": "В ИГРЕ",
	"Downtown": "Центр города", "KNOCKED OUT!": "ВЫ ВЫБЫЛИ!", "Streets, blocks and alleys": "Улицы, кварталы и переулки",
}

const TABLES := {"ru": RU}


func _ready() -> void:
	for loc in TABLES.keys():
		var t := Translation.new()
		t.locale = loc
		var table: Dictionary = TABLES[loc]
		for key in table.keys():
			t.add_message(key, table[key])
		TranslationServer.add_translation(t)
	apply(current())


func current() -> String:
	var saved := str(SaveManager.get_setting("language", ""))
	if saved != "":
		return saved
	return "ru" if OS.get_locale_language() == "ru" else "en"


func apply(code: String) -> void:
	TranslationServer.set_locale(code)


func set_language(code: String) -> void:
	SaveManager.set_setting("language", code)
	apply(code)


## Translate from static code (no Object.tr() there).
static func t(text: String) -> String:
	return TranslationServer.translate(text)
