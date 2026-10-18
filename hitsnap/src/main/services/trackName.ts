// Pure (no Node APIs), so the UI tests can cover it too.

const basename = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? ''

/** "01 - Artist - Title", "Artist – Title", or just "Title" inside an artist folder. */
export function parseTrackName(file: string, parentFolder: string): { artist: string; title: string } {
  const name = basename(file)
    .replace(/\.[^.]+$/, '')
    .replace(/_/g, ' ')
    .replace(/^\s*\d{1,3}\s*[-.)]?\s+/, '')
    .trim()
  const parts = name.split(/\s+[-–—]\s+/)
  if (parts.length >= 2) return { artist: parts[0].trim(), title: parts.slice(1).join(' - ').trim() }
  return { artist: basename(parentFolder) || 'Неизвестный исполнитель', title: name }
}
