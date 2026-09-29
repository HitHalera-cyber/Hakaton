// Текстовая табулатура: верхняя струна сверху, как принято в табах.

import type { Board } from '../music/fretboard';
import { pcName } from '../music/notes';

function cell(board: Board, s: number, capo: number): string {
  const st = board[s];
  if (!st || st.muted) return 'x';
  const pos = [...(st.open ? [capo] : []), ...st.frets.filter((f) => f > capo)];
  if (pos.length === 0) return '-';
  return pos.join('/');
}

export interface TabColumn {
  symbol: string;
  board: Board;
}

/** Табулатура одного или нескольких аккордов (последовательность — столбцами). */
export function makeTab(columns: TabColumn[], tuning: number[], capo = 0, title?: string): string {
  const labels = tuning.map((m) => pcName(m));
  const labelW = Math.max(...labels.map((l) => l.length));
  const lines: string[] = [];
  if (title) lines.push(title);
  if (capo > 0) lines.push(`Каподастр: ${capo} лад`);

  const widths = columns.map((c) => Math.max(c.symbol.length, ...tuning.map((_, s) => cell(c.board, s, capo).length)) + 2);
  lines.push(' '.repeat(labelW + 2) + columns.map((c, i) => c.symbol.padEnd(widths[i] + 1)).join(''));
  for (let s = tuning.length - 1; s >= 0; s--) {
    let row = labels[s].padEnd(labelW) + '|-';
    columns.forEach((c, i) => {
      row += cell(c.board, s, capo).padEnd(widths[i], '-') + '|';
    });
    lines.push(row);
  }
  return lines.join('\n');
}
