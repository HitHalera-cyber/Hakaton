"""Генератор тем «Навь» (славянское тёмное фэнтези) для src/styles/themes.css.

Все варианты используют общую структуру (плетёнка по верху панелей, бронзовые накладки в углах,
кайма меню, тлеющие точки грифа), а отличаются палитрой, орнаментом и пейзажем по низу окна.
Запуск: python3 tools/nav-themes.py — перезаписывает раздел «Навь» в конце themes.css.
"""
import random
import re
import urllib.parse
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / 'src/styles/themes.css'
MARK = '/* ---------- 11. Навь'


def enc(svg: str) -> str:
    return 'url("data:image/svg+xml,' + urllib.parse.quote(svg, safe="='/: ,") + '")'


def plait(a, b, gem):
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='32' height='12'>"
            f"<path d='M0 6C4 0 12 0 16 6S28 12 32 6' fill='none' stroke='{a}' stroke-width='1.4'/>"
            f"<path d='M0 6C4 12 12 12 16 6S28 0 32 6' fill='none' stroke='{b}' stroke-width='1.4'/>"
            f"<path d='M16 3.2 18.8 6 16 8.8 13.2 6Z' fill='{gem}'/>"
            f"<path d='M0 3.2 2.8 6 0 8.8ZM32 3.2 29.2 6 32 8.8Z' fill='{a}'/></svg>")


def rune(a, b, gem):
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='10' height='36'>"
            f"<rect x='0' width='1' height='36' fill='{b}'/><rect x='9' width='1' height='36' fill='{b}'/>"
            f"<path d='M5 4 8 9 5 14 2 9Z' fill='none' stroke='{a}' stroke-width='1'/>"
            f"<path d='M5 7.5 6.5 9 5 10.5 3.5 9Z' fill='{gem}'/>"
            f"<path d='M3 20 7 24M7 20 3 24M5 27v6' stroke='{a}' stroke-width='1'/></svg>")


def corner(rot, a, b, rivet):
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20'>"
            f"<g transform='rotate({rot} 10 10)'><path d='M2 18V2H18' fill='none' stroke='{a}' stroke-width='2'/>"
            f"<path d='M5 14V5H14' fill='none' stroke='{b}' stroke-width='1'/><circle cx='5' cy='5' r='1.6' fill='{rivet}'/></g></svg>")


def spruce_forest(fill, snow=None, seed=7):
    random.seed(seed)
    trees, caps = [], []
    x = 0
    while x < 600:
        h = random.randint(45, 110)
        w = h * 0.42
        base, top, cx = 140, 140 - h, x + h * 0.21
        right = [(cx, top)]
        for t in range(1, 5):
            y = top + h * t / 4 * 0.95
            hw = w / 2 * t / 4
            right += [(cx + hw, y), (cx + hw * 0.45, y)]
            if snow:  # снежные шапки на ярусах
                caps.append(f'M{cx - hw * 0.9:.1f} {y - 1:.1f} {cx:.1f} {y - h / 4 * 0.55:.1f} {cx + hw * 0.9:.1f} {y - 1:.1f}Z')
        left = [(2 * cx - px, py) for px, py in reversed(right[1:])]
        poly = right + [(cx + 3, base), (cx - 3, base)] + left
        trees.append('M' + ' '.join(f'{px:.1f} {py:.1f}' for px, py in poly) + 'Z')
        x += random.randint(14, 34)
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='600' height='140'><path d='{''.join(trees)}' fill='{fill}'/>"
    if snow:
        svg += f"<path d='{''.join(caps)}' fill='{snow}' opacity='0.55'/>"
    return svg + '</svg>'


def swamp(fill, seed=3):
    """Камыш, рогоз и сухие деревья над топью."""
    random.seed(seed)
    parts = []
    for i in range(70):
        x = random.uniform(0, 600)
        h = random.uniform(30, 75)
        bend = random.uniform(-8, 8)
        parts.append(f"<path d='M{x:.1f} 140Q{x + bend / 2:.1f} {140 - h / 2:.1f} {x + bend:.1f} {140 - h:.1f}' stroke='{fill}' stroke-width='{random.uniform(1.2, 2.4):.1f}' fill='none'/>")
        if random.random() < 0.35:
            parts.append(f"<rect x='{x + bend - 2:.1f}' y='{140 - h - 2:.1f}' width='4' height='13' rx='2' fill='{fill}'/>")
    for x in (90, 330, 510):  # сухие деревья
        h = random.randint(95, 125)
        parts.append(f"<path d='M{x} 140L{x + 2} {140 - h}M{x + 1} {150 - h * 0.6}l-22 -18M{x + 1} {145 - h * 0.8}l18 -14M{x + 1} {160 - h * 0.45}l16 -10' stroke='{fill}' stroke-width='4' stroke-linecap='round' fill='none'/>")
    return "<svg xmlns='http://www.w3.org/2000/svg' width='600' height='140'>" + ''.join(parts) + '</svg>'


def dead_forest(fill, seed=11):
    """Кривые голые деревья Кощеева царства."""
    random.seed(seed)
    parts = []
    x = 10
    while x < 600:
        h = random.randint(60, 125)
        lean = random.uniform(-10, 10)
        d = f'M{x:.0f} 140Q{x + lean:.0f} {140 - h / 2:.0f} {x + lean * 1.5:.0f} {140 - h:.0f}'
        for k in range(random.randint(3, 5)):
            y = 140 - h * random.uniform(0.35, 0.9)
            bx = x + lean * (140 - y) / h
            dx = random.choice([-1, 1]) * random.uniform(12, 28)
            d += f'M{bx:.0f} {y:.0f}q{dx / 2:.0f} -6 {dx:.0f} -{random.uniform(10, 22):.0f}'
        parts.append(f"<path d='{d}' stroke='{fill}' stroke-width='{random.uniform(2.5, 4.5):.1f}' stroke-linecap='round' fill='none'/>")
        x += random.randint(30, 70)
    return "<svg xmlns='http://www.w3.org/2000/svg' width='600' height='140'>" + ''.join(parts) + '</svg>'


# ---------- Варианты ----------
VARIANTS = [
    dict(id='slavic', head='11. Навь: кровь и бронза — ночной ельник, тлеющие угли',
         bg='#0b0c0e', grad=('#0d0f12', '#0a0b0d', '#111418'), sky='rgba(160, 20, 26, 0.5)', fog='110, 130, 140',
         landscape=spruce_forest('#050607'),
         panel='#141517', panel_grad=('rgba(26, 27, 30, 0.96)', 'rgba(16, 17, 19, 0.96)'), panel2='#1d1e22', border='#4a3d28',
         text='#ddd2bd', text2='#8f8775', accent='#b3121b', accent_text='#f3e7cf', dot='#7d0d12', root='#ff4b2b', midi='#6fb7c9',
         scale='#a88b52', scale_root='#d43b22', side=('#08090b', '#0d0e10'), side_text='#d3c8b2', side_muted='#6f6757',
         side_active='rgba(179, 18, 27, 0.22)', wood=('#0c0908', '#1a1311'), fret='#8a6a3a', nut='#b9ab8e', string='#c6ccd3',
         inlay='#7d0d12', orn=('#8a6a3a', '#5c4526', '#b3121b', '#b08850'), title='#c9a86a', ember='255, 70, 40', ember2='179, 18, 27',
         btn=('#a3121a', '#6d0a10')),
    dict(id='nav-swamp', head='12. Навь · Болото — трясина, камыш и блуждающие огоньки',
         bg='#060d0a', grad=('#07110d', '#050b08', '#0b1511'), sky='rgba(40, 150, 110, 0.35)', fog='90, 150, 120',
         landscape=swamp('#020604'),
         panel='#0f1712', panel_grad=('rgba(18, 29, 23, 0.95)', 'rgba(11, 19, 15, 0.95)'), panel2='#15211a', border='#2f4a3a',
         text='#cfd9c6', text2='#7d9079', accent='#4fe3a0', accent_text='#03170d', dot='#0d4a3a', root='#8affd0', midi='#e0d45a',
         scale='#5c8a5a', scale_root='#4fe3a0', side=('#040907', '#07100c'), side_text='#c3d2bf', side_muted='#5b7060',
         side_active='rgba(79, 227, 160, 0.16)', wood=('#080c08', '#121a12'), fret='#4f7a63', nut='#9fb49a', string='#b8c9bd',
         inlay='#1f7a5a', orn=('#4f7a63', '#2f4a3a', '#4fe3a0', '#6f9a80'), title='#8fc4a0', ember='90, 255, 180', ember2='30, 160, 110',
         btn=('#1d6b4d', '#0e3a2a')),
    dict(id='nav-winter', head='13. Навь · Мара — ледяная ночь, серебро и заснеженный ельник',
         bg='#070b14', grad=('#0a1220', '#070b14', '#0e1726'), sky='rgba(90, 170, 200, 0.28)', fog='190, 215, 240',
         landscape=spruce_forest('#03060c', snow='#dfe9f5', seed=5),
         panel='#0e1522', panel_grad=('rgba(18, 27, 42, 0.95)', 'rgba(11, 17, 28, 0.95)'), panel2='#152035', border='#34465e',
         text='#e3ecf7', text2='#8ea0b8', accent='#8fd3ff', accent_text='#051120', dot='#1d4a73', root='#d4f1ff', midi='#b69cff',
         scale='#5f7fa3', scale_root='#8fd3ff', side=('#050810', '#0a101b'), side_text='#d7e3f2', side_muted='#62748c',
         side_active='rgba(143, 211, 255, 0.16)', wood=('#090d15', '#131a26'), fret='#a8b6c8', nut='#e6eef8', string='#eef4fb',
         inlay='#3a6e9a', orn=('#a8b6c8', '#5f6e82', '#8fd3ff', '#cfd9e6'), title='#c5d7ec', ember='150, 220, 255', ember2='60, 130, 200',
         btn=('#2e6fa3', '#16395c')),
    dict(id='nav-fire', head='14. Навь · Купала — зарево костра за чёрным лесом, золото и искры',
         bg='#0c0705', grad=('#0d0806', '#0a0604', '#1a0d06'), sky='rgba(120, 40, 10, 0.3)', fog='255, 120, 40',
         landscape=spruce_forest('#060302', seed=9),
         panel='#150e0a', panel_grad=('rgba(30, 20, 14, 0.95)', 'rgba(19, 12, 8, 0.95)'), panel2='#22160f', border='#5a3a1c',
         text='#f0dcc0', text2='#a08566', accent='#ff8a1f', accent_text='#1a0b02', dot='#8f3306', root='#ffd23a', midi='#6fc9c0',
         scale='#b8782a', scale_root='#ff8a1f', side=('#0a0503', '#110a06'), side_text='#ecd6b6', side_muted='#7c6247',
         side_active='rgba(255, 138, 31, 0.18)', wood=('#120a06', '#1f130b'), fret='#c98a2a', nut='#e8cf9e', string='#f3e2c8',
         inlay='#b34a0e', orn=('#c98a2a', '#7a4f1c', '#ff5a1f', '#e0a64a'), title='#e8aa4a', ember='255, 140, 30', ember2='220, 60, 10',
         btn=('#d0600e', '#7a2c05'), fog_strength=(0.45, 0.2)),
    dict(id='nav-koschei', head='15. Навь · Кощей — чёрно-фиолетовая тьма, старое золото и аметисты',
         bg='#09070d', grad=('#0d0a13', '#08060c', '#120d1a'), sky='rgba(110, 40, 170, 0.35)', fog='140, 100, 190',
         landscape=dead_forest('#040306'),
         panel='#120f18', panel_grad=('rgba(24, 19, 32, 0.95)', 'rgba(15, 12, 21, 0.95)'), panel2='#1b1624', border='#4a3d24',
         text='#e8e0f0', text2='#968ca8', accent='#d8b44a', accent_text='#140c02', dot='#4b1f6e', root='#f0d27a', midi='#6fc9a0',
         scale='#6f4f9a', scale_root='#d8b44a', side=('#060409', '#0c0912'), side_text='#e0d6ea', side_muted='#6e6480',
         side_active='rgba(143, 63, 209, 0.22)', wood=('#0b0810', '#17111f'), fret='#b8962e', nut='#e6dcc0', string='#d8d0e6',
         inlay='#6f2fa3', orn=('#b8962e', '#6b5620', '#9b4fe0', '#d8b44a'), title='#dcbc5a', ember='190, 110, 255', ember2='110, 40, 170',
         btn=('#7a3fb0', '#3d1c5e')),
]


def block(v):
    sel = f"[data-theme='{v['id']}']"
    a, b, gem, rivet = v['orn']
    f1, f2 = v.get('fog_strength', (0.22, 0.1))
    corners = ', '.join([f'{enc(corner(0, a, b, rivet))} top left no-repeat', f'{enc(corner(90, a, b, rivet))} top right no-repeat',
                         f'{enc(corner(270, a, b, rivet))} bottom left no-repeat', f'{enc(corner(180, a, b, rivet))} bottom right no-repeat'])
    return f'''
/* ---------- {v['head']} ---------- */
{sel} {{
  --bg: {v['bg']};
  --app-bg: {enc(v['landscape'])} bottom left / 600px 140px repeat-x fixed,
    linear-gradient(0deg, transparent 0, rgba({v['fog']}, {f1}) 90px, rgba({v['fog']}, {f2}) 150px, transparent 230px) bottom / 100% 240px no-repeat fixed,
    radial-gradient(ellipse 60% 45% at 85% 0%, {v['sky']}, transparent 70%),
    linear-gradient(180deg, {v['grad'][0]} 0%, {v['grad'][1]} 60%, {v['grad'][2]} 100%);
  --bg-2: {v['panel']};
  --panel: {v['panel']};
  --panel-bg: linear-gradient(180deg, {v['panel_grad'][0]}, {v['panel_grad'][1]});
  --panel-2: {v['panel2']};
  --border: {v['border']};
  --text: {v['text']};
  --text-2: {v['text2']};
  --accent: {v['accent']};
  --accent-text: {v['accent_text']};
  --dot: {v['dot']};
  --dot-text: {v['text']};
  --root: {v['root']};
  --midi: {v['midi']};
  --scale: {v['scale']};
  --scale-root: {v['scale_root']};
  --hover: rgba({v['ember2']}, 0.18);
  --tt-bg: #050507;
  --side-bg: linear-gradient(180deg, {v['side'][0]}, {v['side'][1]});
  --side-text: {v['side_text']};
  --side-muted: {v['side_muted']};
  --side-active: {v['side_active']};
  --side-active-text: {v['text']};
  --wood-1: {v['wood'][0]};
  --wood-2: {v['wood'][1]};
  --fret: {v['fret']};
  --nut: {v['nut']};
  --string: {v['string']};
  --inlay: {v['inlay']};
  --glow: 0 0 14px rgba({v['ember']}, 0.55), 0 0 32px rgba({v['ember2']}, 0.35);
  --nav-title: {v['title']};
  --nav-ornament: {a};
  --nav-ember: {v['ember']};
  --nav-ember-2: {v['ember2']};
  --nav-btn: linear-gradient(180deg, {v['btn'][0]}, {v['btn'][1]});
  --plait: {enc(plait(a, b, gem))};
  --rune: {enc(rune(a, b, gem))};
  --corners: {corners};
}}
'''


COMMON = '''
/* ---------- Навь: общая структура всех вариантов ---------- */
:is([data-theme='slavic'], [data-theme^='nav-']) {
  --ok: #6f9e5a;
  --warn: #c9923a;
  --danger: #e0352b;
  --font-ui: 'Alegreya', 'PT Serif', Georgia, serif;
  --font-display: 'Cormorant SC', 'Alegreya', serif;
  --font-serif: 'Alegreya', Georgia, serif;
  --font-symbol: 'Alegreya', Georgia, serif;
  --fs: 15px;
  --display-weight: 700;
  --display-scale: 1.05;
  --title-case: none;
  --title-spacing: 0.14em;
  --radius: 2px;
  --radius-sm: 2px;
  --radius-pill: 2px;
  --bw: 1px;
  --shadow: 0 0 0 1px rgba(0, 0, 0, 0.6), 0 14px 40px rgba(0, 0, 0, 0.65);
  color-scheme: dark;
}
/* Плетёнка по верху панелей и накладки в углах. */
:is([data-theme='slavic'], [data-theme^='nav-']) .panel {
  position: relative;
  padding-top: 26px;
}
:is([data-theme='slavic'], [data-theme^='nav-']) .panel::before {
  content: '';
  position: absolute;
  top: 7px;
  left: 26px;
  right: 26px;
  height: 12px;
  background: var(--plait) repeat-x center / auto 12px;
  opacity: 0.9;
  pointer-events: none;
}
:is([data-theme='slavic'], [data-theme^='nav-']) .panel::after {
  content: '';
  position: absolute;
  inset: 3px;
  background: var(--corners);
  pointer-events: none;
}
:is([data-theme='slavic'], [data-theme^='nav-']) .sidebar {
  border-right: 10px solid transparent;
  border-image: var(--rune) 0 10 0 0 / 0 10px 0 0 round;
}
:is([data-theme='slavic'], [data-theme^='nav-']) :is(.brand h1, .tool-title, .panel h3) {
  color: var(--nav-title);
}
:is([data-theme='slavic'], [data-theme^='nav-']) .brand h1 {
  letter-spacing: 0.08em;
}
:is([data-theme='slavic'], [data-theme^='nav-']) .nav-title {
  font-family: var(--font-display);
  font-size: 13px;
  letter-spacing: 0.2em;
  text-transform: none;
  color: var(--nav-ornament);
}
:is([data-theme='slavic'], [data-theme^='nav-']) .btn {
  background: linear-gradient(180deg, color-mix(in srgb, var(--panel-2) 90%, white), var(--panel-2));
}
:is([data-theme='slavic'], [data-theme^='nav-']) .btn.primary {
  background: var(--nav-btn);
  color: var(--text);
  border-color: var(--nav-ornament);
  box-shadow: 0 0 16px rgba(var(--nav-ember-2), 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
/* Тлеющие точки на грифе и «дышащее» название аккорда. */
:is([data-theme='slavic'], [data-theme^='nav-']) .fretboard .dot circle {
  stroke: var(--nav-ornament);
  stroke-width: 1.5;
  filter: drop-shadow(0 0 5px rgba(var(--nav-ember), 0.9)) drop-shadow(0 0 12px rgba(var(--nav-ember-2), 0.6));
}
:is([data-theme='slavic'], [data-theme^='nav-']) .fretboard .dot.root text {
  fill: var(--bg);
}
:is([data-theme='slavic'], [data-theme^='nav-']) .fretboard .inlay {
  filter: drop-shadow(0 0 4px rgba(var(--nav-ember-2), 0.8));
}
:is([data-theme='slavic'], [data-theme^='nav-']) .chord-symbol {
  animation: nav-ember 3.2s ease-in-out infinite;
}
@keyframes nav-ember {
  50% {
    text-shadow: 0 0 8px rgba(var(--nav-ember), 0.35), 0 0 20px rgba(var(--nav-ember-2), 0.2);
  }
}
'''

css = CSS.read_text()
css = css[: css.index(MARK)] if MARK in css else css
CSS.write_text(css.rstrip() + '\n' + ''.join(block(v) for v in VARIANTS) + COMMON)
print('ok', len(VARIANTS))
