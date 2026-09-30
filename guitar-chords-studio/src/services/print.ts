// Печать и PDF. Печатается только блок .print-root (стили @media print в styles/print.css).

export async function printSong(title: string, mode: 'print' | 'pdf') {
  document.body.classList.add('printing');
  const prevTitle = document.title;
  document.title = title;
  try {
    if (mode === 'pdf' && window.gc?.printToPdf) await window.gc.printToPdf(title);
    else window.print();
  } finally {
    document.title = prevTitle;
    document.body.classList.remove('printing');
  }
}
