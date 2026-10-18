// Text normalisation for searching: case, accents, ё/е, Cyrillic ⇄ Latin.

const CYR_TO_LAT: Record<string, string> = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z', и: 'i', й: 'y',
  к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f',
  х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya'
}

// Same physical keys on the ЙЦУКЕН and QWERTY layouts: "rbyj" typed with the
// wrong layout still finds «Кино».
const QWERTY = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"
const JCUKEN = 'йцукенгшщзхъфывапролджэячсмитьбюё'
const LAT_KEY_TO_CYR = new Map([...QWERTY].map((ch, i) => [ch, JCUKEN[i]]))
const CYR_KEY_TO_LAT = new Map([...JCUKEN].map((ch, i) => [ch, QWERTY[i]]))

/** Lower-case, strip accents and punctuation, collapse spaces. */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/й/g, '\u0000') // keep й through NFKD (it would decompose into и + breve)
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/\u0000/g, 'й')
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9а-я\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function translit(text: string): string {
  return [...text].map((ch) => CYR_TO_LAT[ch] ?? ch).join('')
}

/** Re-types the text as if it had been typed with the other keyboard layout. */
export function swapLayout(text: string): string {
  const lower = text.toLowerCase()
  const cyr = /[а-яё]/.test(lower)
  return [...lower].map((ch) => (cyr ? CYR_KEY_TO_LAT.get(ch) : LAT_KEY_TO_CYR.get(ch)) ?? ch).join('')
}

/** Levenshtein distance, bailing out early once it exceeds `max`. */
export function editDistance(a: string, b: string, max = 2): number {
  if (Math.abs(a.length - b.length) > max) return max + 1
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    const cur = [i]
    let rowMin = i
    for (let j = 1; j <= b.length; j++) {
      const v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
      cur.push(v)
      rowMin = Math.min(rowMin, v)
    }
    if (rowMin > max) return max + 1
    prev = cur
  }
  return prev[b.length]
}

/** A word spelled the way it sounds, in Latin letters: «джексон» → "jekson", "jackson" → "jakson". */
export function soundForm(word: string): string {
  return translit(normalize(word))
    .replace(/dzh|zh|dj/g, 'j')
    .replace(/kh/g, 'h')
    .replace(/qu/g, 'kv')
    .replace(/c(?=[eiy])/g, 's')
    .replace(/ck|ch|q|c/g, 'k')
    .replace(/ph/g, 'f')
    .replace(/sh|sch/g, 's')
    .replace(/ts|tz/g, 's')
    .replace(/x/g, 'ks')
    .replace(/w/g, 'v')
    .replace(/z/g, 's')
    .replace(/(.)\1+/g, '$1')
}

/**
 * Rough "how it sounds" key of a word, for names typed in the other alphabet:
 * «леди гага» → "ld gg", the same as "lady gaga". Consonants only (a leading
 * vowel is kept).
 */
export function soundKey(word: string): string {
  const w = soundForm(word)
  return (w[0] ?? '') + w.slice(1).replace(/[aeiouy]/g, '')
}
