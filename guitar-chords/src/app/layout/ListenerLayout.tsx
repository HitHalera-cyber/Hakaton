import { CircleOfFifths } from '../../features/circle/CircleOfFifths';
import { ListenerStage } from '../../features/listen/ListenerStage';
import { useApp } from '../AppContext';
import { circleProps } from '../panels';
import { BoardCard } from './BoardCard';
import { Drawer, RailFrame } from './common';
import { useDrawer } from './useDrawer';

/** «Слушатель»: для игры на живой гитаре — крупно услышанный аккорд, квинтовый круг, история и гриф. */
export function ListenerLayout() {
  const app = useApp();
  const drawer = useDrawer();
  const { listener, guitar } = app;
  const showChord = (c: { rootPc: number; templateId: string; bassPc?: number }) => guitar.showChord(c.rootPc, c.templateId, c.bassPc);

  return (
    <RailFrame active={drawer.tab} onNav={drawer.show}>
      <main className="workspace listener">
        <ListenerStage
          listener={listener}
          board={guitar.result}
          voicing={(c) => guitar.voicingFor(c.rootPc, c.templateId, c.bassPc)}
          capo={guitar.capo}
        />
        <section className="panel listener-circle">
          <CircleOfFifths compact size={340} {...circleProps(app)} />
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
                <button key={i} className={i === 0 ? 'on' : ''} onClick={() => showChord(h)} title={`${h.nameRu} — показать на грифе`}>
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
      {drawer.tab && <Drawer tab={drawer.tab} onClose={drawer.close} />}
    </RailFrame>
  );
}
