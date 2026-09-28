// Аккордовая диаграмма (как в песенниках) на canvas — для сохранения в PNG.

import type { Board } from '../music/fretboard';
import type { Fingering } from '../music/fingering';
import { fingerKey } from '../music/fingering';

export interface DiagramInput {
  board: Board;
  capo: number;
  title: string;
  subtitle?: string;
  fingering?: Fingering;
  stringLabels: string[];
}

/** Первый показываемый лад и число ладов в окне диаграммы. */
export function diagramWindow(board: Board, capo: number): { start: number; rows: number } {
  const frets = board.flatMap((s) => (s.muted ? [] : s.frets.filter((f) => f > capo)));
  if (frets.length === 0) return { start: capo + 1, rows: 4 };
  const min = Math.min(...frets);
  const max = Math.max(...frets);
  const start = max <= Math.max(4, capo + 4) ? capo + 1 : min;
  return { start, rows: Math.max(4, max - start + 1) };
}

export function renderDiagramPng(input: DiagramInput, scale = 2): Promise<Blob> {
  const n = input.board.length;
  const { start, rows } = diagramWindow(input.board, input.capo);
  const gap = 34;
  const rowH = 40;
  const left = 50;
  const top = 118;
  const w = left * 2 + gap * (n - 1);
  const h = top + rowH * rows + 70;

  const canvas = document.createElement('canvas');
  canvas.width = w * scale;
  canvas.height = h * scale;
  const ctx = canvas.getContext('2d')!;
  ctx.scale(scale, scale);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  ctx.fillStyle = '#111827';
  ctx.font = 'bold 30px "Segoe UI", Arial, sans-serif';
  ctx.fillText(input.title, w / 2, 30);
  if (input.subtitle) {
    ctx.font = '14px "Segoe UI", Arial, sans-serif';
    ctx.fillStyle = '#4b5563';
    ctx.fillText(input.subtitle, w / 2, 58, w - 16);
  }

  const x = (s: number) => left + s * gap;
  const y = (row: number) => top + row * rowH;

  // Порожек или номер первого лада.
  ctx.strokeStyle = '#111827';
  if (start === 1) {
    ctx.lineWidth = 7;
    ctx.beginPath();
    ctx.moveTo(x(0) - 2, y(0));
    ctx.lineTo(x(n - 1) + 2, y(0));
    ctx.stroke();
  } else {
    ctx.font = 'bold 15px "Segoe UI", Arial, sans-serif';
    ctx.fillStyle = '#111827';
    ctx.fillText(`${start}`, x(0) - 26, y(0) + rowH / 2);
  }
  ctx.lineWidth = 1.5;
  for (let r = 0; r <= rows; r++) {
    ctx.beginPath();
    ctx.moveTo(x(0), y(r));
    ctx.lineTo(x(n - 1), y(r));
    ctx.stroke();
  }
  for (let s = 0; s < n; s++) {
    ctx.beginPath();
    ctx.moveTo(x(s), y(0));
    ctx.lineTo(x(s), y(rows));
    ctx.stroke();
  }

  // Баррэ.
  const barre = input.fingering?.barre;
  if (barre && barre.fret >= start && barre.fret < start + rows) {
    const cy = y(barre.fret - start) + rowH / 2;
    ctx.fillStyle = '#111827';
    ctx.beginPath();
    ctx.roundRect(x(barre.fromString) - 12, cy - 12, x(barre.toString) - x(barre.fromString) + 24, 24, 12);
    ctx.fill();
  }

  input.board.forEach((st, s) => {
    const cy = y(0) - 18;
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#111827';
    if (st.muted) {
      ctx.beginPath();
      ctx.moveTo(x(s) - 7, cy - 7);
      ctx.lineTo(x(s) + 7, cy + 7);
      ctx.moveTo(x(s) + 7, cy - 7);
      ctx.lineTo(x(s) - 7, cy + 7);
      ctx.stroke();
      return;
    }
    if (st.open) {
      ctx.beginPath();
      ctx.arc(x(s), cy, 7, 0, Math.PI * 2);
      ctx.stroke();
    }
    for (const f of st.frets) {
      if (f <= input.capo || f < start || f >= start + rows) continue;
      const cx = x(s);
      const cyy = y(f - start) + rowH / 2;
      ctx.fillStyle = '#111827';
      ctx.beginPath();
      ctx.arc(cx, cyy, 13, 0, Math.PI * 2);
      ctx.fill();
      const finger = input.fingering?.fingers.get(fingerKey(s, f));
      if (finger) {
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px "Segoe UI", Arial, sans-serif';
        ctx.fillText(String(finger), cx, cyy + 1);
      }
    }
  });

  ctx.fillStyle = '#374151';
  ctx.font = '14px "Segoe UI", Arial, sans-serif';
  input.stringLabels.forEach((l, s) => ctx.fillText(l, x(s), y(rows) + 20));
  if (input.capo > 0) {
    ctx.font = '13px "Segoe UI", Arial, sans-serif';
    ctx.fillText(`Каподастр: ${input.capo} лад`, w / 2, y(rows) + 46);
  }

  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('PNG'))), 'image/png'));
}
