import { app } from 'electron'
import { readFileSync } from 'node:fs'
import { rename, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

// A tiny key-value store backing the UI's persisted state (settings, stats,
// user songs). One JSON file in userData, written atomically.

const file = (): string => join(app.getPath('userData'), 'hitsnap-data.json')

let data: Record<string, string> | null = null
let writing: Promise<void> = Promise.resolve()

function load(): Record<string, string> {
  if (data) return data
  try {
    data = JSON.parse(readFileSync(file(), 'utf8')) as Record<string, string>
  } catch {
    data = {}
  }
  return data
}

function flush(): Promise<void> {
  const snapshot = JSON.stringify(load())
  writing = writing.catch(() => undefined).then(async () => {
    const tmp = `${file()}.tmp`
    await writeFile(tmp, snapshot, 'utf8')
    await rename(tmp, file())
  })
  return writing
}

export const storage = {
  get: (key: string): string | null => load()[key] ?? null,
  set: (key: string, value: string): Promise<void> => {
    load()[key] = value
    return flush()
  },
  remove: (key: string): Promise<void> => {
    delete load()[key]
    return flush()
  }
}
