import { midiName } from '../../core/music/notes';
import { useGuitar } from '../../store';
import { ChordDiagram } from '../../ui/ChordDiagram';
import { symClass } from './symClass';
import type { ChordListener } from './useListener';

/** Режим «По струнам»: какие щипки услышаны и итоговая точная аппликатура. */
export function StringsView({ listener }: { listener: ChordListener }) {
  const g = useGuitar();
  const { strings, active } = listener;
  const n = g.strings.length;
  const r = strings.result;
  return (
    <div className="strings-view">
      {r ? (
        <div className="strings-result">
          <div>
            <div className={`listen-symbol ${symClass(r.symbol)}`}>{r.symbol}</div>
            <div className="listen-ru">{r.nameRu}</div>
            <div className="strings-tab" title="Аппликатура от 6-й струны к 1-й: x — не звучит, 0 — открытая">
              {r.tab}
            </div>
            {r.confidence < 0.4 && <small className="hint">Струны можно разложить по-разному — проверьте на грифе</small>}
          </div>
          <ChordDiagram frets={r.frets} capo={g.capo} size={120} />
        </div>
      ) : (
        <div className="hint center">
          {active
            ? strings.plucks.length
              ? 'Дальше по одной струне…'
              : `Зажмите аккорд и проведите по струнам по одной — от ${n}-й (басовой) к 1-й`
            : 'Нажмите «Начать слушать», зажмите аккорд и сыграйте струны по одной'}
        </div>
      )}
      <div className="strings-plucks" title="Услышанные щипки по порядку">
        {Array.from({ length: n }, (_, i) => {
          const p = strings.plucks[i];
          const state = i < strings.plucks.length ? (p == null ? 'dead' : 'ok') : i === strings.plucks.length && active ? 'next' : '';
          return (
            <span key={i} className={state}>
              {i < strings.plucks.length ? (p == null ? '✕' : midiName(p)) : '·'}
            </span>
          );
        })}
      </div>
    </div>
  );
}
