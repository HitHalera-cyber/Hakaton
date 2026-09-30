import { useCircleProps } from '../../modules/circle/useCircle';
import { ListenerStage } from '../../modules/listen/ListenerStage';
import { useListener } from '../../modules/listen/useListener';
import { store, useGuitar, usePick } from '../../store';
import { CircleOfFifths } from '../../ui/CircleOfFifths';
import { BoardCard } from '../BoardCard';
import { Frame } from './Frame';

/** «Слушатель»: для игры на живой гитаре — крупно услышанный аккорд, квинтовый круг, история и гриф. */
export function ListenerLayout() {
  const listener = useListener();
  const g = useGuitar();
  const circle = useCircleProps();
  const { drawerOpen, tab } = usePick((s) => ({ drawerOpen: s.drawerOpen, tab: s.settings.view.tab }));
  const st = store.getState();
  return (
    <Frame compact active={drawerOpen ? tab : null} onOpen={(id) => st.openModule(id)}>
      <main className="workspace listener">
        <ListenerStage
          listener={listener}
          board={g.result}
          voicing={(c) => st.voicingFor(c.rootPc, c.templateId, c.bassPc)}
          capo={g.capo}
        />
        <section className="panel listener-circle">
          <CircleOfFifths compact size={340} {...circle} />
        </section>
        <section className="panel listener-history">
          <h3>
            Сыграно
            {listener.history.length > 0 && (
              <button className="link" onClick={listener.clearHistory}>
                очистить
              </button>
            )}
          </h3>
          {listener.history.length ? (
            <div className="heard-list">
              {listener.history.map((h, i) => (
                <button
                  key={i}
                  className={i === 0 ? 'on' : ''}
                  onClick={() => st.showChord(h.rootPc, h.templateId, h.bassPc)}
                  title={`${h.nameRu} — показать на грифе`}
                >
                  {h.symbol}
                </button>
              ))}
            </div>
          ) : (
            <p className="hint">Здесь появятся аккорды, которые вы сыграли</p>
          )}
        </section>
        <BoardCard />
      </main>
    </Frame>
  );
}
