import '../../ui/practice.css';
import { lastDays, streak, totalMinutes } from '../../core/practice/stats';
import { LEARN_THRESHOLD } from '../../store/practice';
import { todayKey } from '../../store/model';
import { usePick } from '../../store';
import type { ModuleDef } from '../types';

const minutesText = (m: number) => (m >= 60 ? `${Math.floor(m / 60)} ч ${m % 60} мин` : `${m} мин`);

/** Статистика занятий: время, серия дней подряд, выученные аккорды, график по дням. */
function StatsView() {
  const { practice, reset } = usePick((s) => ({ practice: s.practice, reset: s.resetPractice }));
  const today = practice.days[todayKey()];
  const days = lastDays(practice.days, 14);
  const max = Math.max(10, ...days.map((d) => d.minutes));
  const inProgress = Object.entries(practice.heardCount)
    .filter(([c]) => !practice.learned.includes(c))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  return (
    <div className="tab-body">
      <div className="pr-cards">
        <div className="pr-card">
          <small>Сегодня</small>
          <span className="pr-big">{today && today.seconds > 0 && today.seconds < 60 ? '<1' : Math.round((today?.seconds ?? 0) / 60)}</span>
          <small>минут занятий</small>
        </div>
        <div className="pr-card">
          <small>Серия</small>
          <span className="pr-big">{streak(practice.days)}</span>
          <small>дней подряд</small>
        </div>
        <div className="pr-card">
          <small>Всего</small>
          <b>{minutesText(totalMinutes(practice.days))}</b>
        </div>
        <div className="pr-card">
          <small>Выучено аккордов</small>
          <b>{practice.learned.length}</b>
        </div>
      </div>

      <h3>Последние две недели, минут</h3>
      <div className="st-chart">
        {days.map((d) => (
          <div key={d.key} className="st-day" title={`${d.label}: ${d.minutes} мин`}>
            <span className="st-val">{d.minutes || ''}</span>
            <span className="st-bar" style={{ height: `${(d.minutes / max) * 100}%` }} />
            <small>{d.label}</small>
          </div>
        ))}
      </div>

      <h3>Выученные аккорды</h3>
      {practice.learned.length ? (
        <div className="pr-chips">
          {practice.learned.map((c) => (
            <span key={c} className="pr-chip">
              ✓ {c}
            </span>
          ))}
        </div>
      ) : (
        <p className="hint">
          Аккорд считается выученным, когда вы чисто сыграли его на гитаре {LEARN_THRESHOLD} раз (раздел «Слушать гитару», уроки, «Смены
          аккордов»).
        </p>
      )}
      {inProgress.length > 0 && (
        <>
          <h3>На пути к выученным</h3>
          <div className="pr-chips">
            {inProgress.map(([c, n]) => (
              <span key={c} className="pr-chip" title={`Сыграно ${n} из ${LEARN_THRESHOLD}`}>
                {c} · {n}/{LEARN_THRESHOLD}
              </span>
            ))}
          </div>
        </>
      )}

      <h3>Рекорды</h3>
      <div className="pr-chips">
        {Object.entries(practice.changesBest).map(([pair, v]) => (
          <span key={pair} className="pr-chip">
            {pair}: {v} смен/мин
          </span>
        ))}
        {practice.rhythmBest != null && <span className="pr-chip">Ритм: ±{practice.rhythmBest} мс</span>}
        {!Object.keys(practice.changesBest).length && practice.rhythmBest == null && (
          <span className="hint">Пока нет — загляните в «Смены аккордов» и «Ритм».</span>
        )}
      </div>

      <div className="pr-row">
        <button
          className="btn small danger"
          onClick={() => {
            if (confirm('Сбросить всю статистику занятий?')) reset();
          }}
        >
          Сбросить статистику
        </button>
        <span className="hint">Время считается, пока программа открыта и вы играете (микрофон, метроном, песня) или что-то нажимаете.</span>
      </div>
    </div>
  );
}

export const statsModule: ModuleDef = {
  id: 'stats',
  title: 'Статистика',
  icon: '📈',
  group: 'practice',
  description: 'Время занятий, серия дней подряд, выученные аккорды, рекорды',
  keywords: ['прогресс', 'время', 'серия', 'выучено'],
  View: StatsView,
  isNew: true,
};
