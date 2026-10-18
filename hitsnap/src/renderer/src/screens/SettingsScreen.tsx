import { Maximize2, Trash2, Volume1, Volume2, VolumeX } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Button, Card, cx, SectionTitle, Segmented, Toggle } from '@/components/ui'
import { api } from '@/lib/api'
import { audio } from '@/lib/audio'
import { formatBytes } from '@/lib/format'
import type { Difficulty } from '@/lib/game'
import { useSettings, type Accent, type ThemePref } from '@/store/settings'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'

const ACCENTS: Array<{ id: Accent; label: string; from: string; to: string }> = [
  { id: 'violet', label: 'Неон', from: '#8b5cf6', to: '#ec4899' },
  { id: 'ocean', label: 'Океан', from: '#0ea5e9', to: '#6366f1' },
  { id: 'sunset', label: 'Закат', from: '#f97316', to: '#e11d48' },
  { id: 'lime', label: 'Мята', from: '#16a34a', to: '#0d9488' },
  { id: 'rose', label: 'Роза', from: '#e11d48', to: '#a855f7' }
]

const AVATARS = ['🎧', '🎸', '🥁', '🎹', '🎤', '🎷', '🎺', '🎻', '🪩', '🦄', '🐱', '🦊', '🐼', '🐸', '🦁', '🐙', '👽', '🤖', '👑', '🔥', '⭐', '🌈', '🍕', '🚀']

function Row({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6 py-4">
      <div>
        <div className="font-medium">{title}</div>
        {hint && <div className="mt-0.5 text-sm text-muted">{hint}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

export function SettingsScreen() {
  const s = useSettings()
  const resetStats = useStats((st) => st.reset)
  const toast = useUi((u) => u.toast)
  const [cache, setCache] = useState<{ files: number; bytes: number } | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)

  useEffect(() => {
    void api.cacheInfo().then(setCache)
  }, [])

  const VolumeIcon = s.volume === 0 ? VolumeX : s.volume < 0.5 ? Volume1 : Volume2

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-3xl font-black tracking-tight">Настройки</h1>

      <SectionTitle>Профиль</SectionTitle>
      <Card className="mb-8 p-6">
        <div className="flex items-center gap-5">
          <div className="bg-gradient-accent flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl text-4xl shadow-lg shadow-accent/30">{s.profileEmoji}</div>
          <div className="min-w-0 flex-1">
            <label className="mb-1.5 block text-sm font-medium" htmlFor="profile-name">
              Как вас зовут?
            </label>
            <input
              id="profile-name"
              value={s.profileName}
              maxLength={24}
              placeholder="Имя или ник"
              onChange={(e) => {
                const name = e.target.value
                // The first party player follows the profile name until renamed by hand.
                const first = s.players[0]
                const follows = first && (first.name === 'Игрок 1' || first.name === s.profileName)
                s.update({ profileName: name, players: follows ? [{ ...first, name: name.trim() || 'Игрок 1' }, ...s.players.slice(1)] : s.players })
              }}
              className="h-11 w-full rounded-xl border border-line bg-fg/5 px-4 outline-none focus:border-accent"
            />
            <div className="mt-1.5 text-xs text-muted">Имя видно в меню, в «Дуэли» и первым игроком на «Вечеринке».</div>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-1.5">
          {AVATARS.map((e) => (
            <button
              key={e}
              onClick={() => s.update({ profileEmoji: e })}
              className={cx(
                'flex h-10 w-10 items-center justify-center rounded-xl text-xl transition cursor-pointer',
                s.profileEmoji === e ? 'bg-accent/15 ring-2 ring-accent' : 'hover:bg-fg/5'
              )}
            >
              {e}
            </button>
          ))}
        </div>
      </Card>

      <SectionTitle>Оформление</SectionTitle>
      <Card className="mb-8 divide-y divide-line px-6">
        <Row title="Тема" hint="«Как в системе» следует за настройками Windows / macOS">
          <Segmented<ThemePref>
            value={s.theme}
            onChange={(theme) => s.update({ theme })}
            options={[
              { value: 'system', label: 'Системная' },
              { value: 'light', label: 'Светлая' },
              { value: 'dark', label: 'Тёмная' }
            ]}
          />
        </Row>
        <Row title="Акцентный цвет">
          <div className="flex gap-2">
            {ACCENTS.map((a) => (
              <button
                key={a.id}
                title={a.label}
                onClick={() => s.update({ accent: a.id })}
                className={cx('h-8 w-8 rounded-full transition cursor-pointer', s.accent === a.id ? 'ring-2 ring-fg ring-offset-2 ring-offset-bg' : 'hover:scale-110')}
                style={{ background: `linear-gradient(135deg, ${a.from}, ${a.to})` }}
              />
            ))}
          </div>
        </Row>
        <Row title="Полный экран" hint="Удобно для «Вечеринки» на большом экране. Клавиша F11">
          <Button variant="secondary" onClick={() => api.toggleFullScreen()}>
            <Maximize2 size={16} /> Переключить
          </Button>
        </Row>
        <Row title="Визуализатор" hint="Анимированный спектр во время звучания">
          <Toggle label="Визуализатор" checked={s.visualizer} onChange={(visualizer) => s.update({ visualizer })} />
        </Row>
      </Card>

      <SectionTitle>Звук</SectionTitle>
      <Card className="mb-8 divide-y divide-line px-6">
        <Row title="Громкость">
          <div className="flex items-center gap-3">
            <VolumeIcon size={18} className="text-muted" />
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={s.volume}
              onChange={(e) => s.update({ volume: Number(e.target.value) })}
              onMouseUp={() => audio.sfx('tick')}
              className="w-48"
            />
            <span className="w-10 text-right text-sm tabular-nums text-muted">{Math.round(s.volume * 100)}%</span>
          </div>
        </Row>
        <Row title="Звуковые эффекты" hint="Сигналы правильного и неправильного ответа">
          <Toggle label="Звуковые эффекты" checked={s.sfx} onChange={(sfx) => s.update({ sfx })} />
        </Row>
        <Row title="Автовоспроизведение" hint="Сразу играть отрывок в начале раунда и после ошибки">
          <Toggle label="Автовоспроизведение" checked={s.autoplay} onChange={(autoplay) => s.update({ autoplay })} />
        </Row>
      </Card>

      <SectionTitle>Игра</SectionTitle>
      <Card className="mb-8 divide-y divide-line px-6">
        <Row title="Сложность" hint="Длина отрывков: 2/5/10 с, 1/3/5 с или 0,5/1/3 с">
          <Segmented<Difficulty>
            value={s.difficulty}
            onChange={(difficulty) => s.update({ difficulty })}
            options={[
              { value: 'easy', label: 'Лёгкая' },
              { value: 'normal', label: 'Обычная' },
              { value: 'hard', label: 'Хардкор' }
            ]}
          />
        </Row>
        <Row title="Раундов в классике">
          <Segmented<number>
            value={s.roundsPerGame}
            onChange={(roundsPerGame) => s.update({ roundsPerGame })}
            options={[5, 10, 15, 20].map((n) => ({ value: n, label: String(n) }))}
          />
        </Row>
      </Card>

      <SectionTitle>Данные</SectionTitle>
      <Card className="mb-8 divide-y divide-line px-6">
        <Row
          title="Кеш превью"
          hint={cache ? `${cache.files} песен на диске · ${formatBytes(cache.bytes)}. Прослушанные песни доступны без интернета.` : 'Считаем…'}
        >
          <Button
            variant="secondary"
            onClick={async () => {
              await api.clearCache()
              setCache(await api.cacheInfo())
              toast({ title: 'Кеш очищен', icon: '🧹' })
            }}
          >
            <Trash2 size={16} /> Очистить
          </Button>
        </Row>
        <Row title="Сбросить статистику" hint="Рекорды, история игр и достижения будут удалены">
          {confirmReset ? (
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setConfirmReset(false)}>
                Отмена
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  resetStats()
                  setConfirmReset(false)
                  toast({ title: 'Статистика сброшена', icon: '🗑️' })
                }}
              >
                Да, сбросить
              </Button>
            </div>
          ) : (
            <Button variant="danger" onClick={() => setConfirmReset(true)}>
              Сбросить
            </Button>
          )}
        </Row>
      </Card>

      <p className="text-center text-xs text-muted">
        HitSnap 1.3 · Превью песен — Deezer и iTunes (30-секундные отрывки, предоставляемые сервисами)
      </p>
    </div>
  )
}
