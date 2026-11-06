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
	"Plastic": "Пластик",
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
