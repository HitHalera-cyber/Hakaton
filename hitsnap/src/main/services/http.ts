import { net } from 'electron'

const TIMEOUT_MS = 12_000

/** fetch via Chromium's network stack (honours system proxy settings) with a timeout. */
async function request(url: string): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const res = await net.fetch(url, { signal: controller.signal })
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`)
    return res
  } finally {
    clearTimeout(timer)
  }
}

export async function getJson<T>(url: string): Promise<T> {
  return (await request(url)).json() as Promise<T>
}

export async function getBytes(url: string): Promise<ArrayBuffer> {
  return (await request(url)).arrayBuffer()
}

/** The final URL after redirects (for share links). */
export async function resolveRedirect(url: string): Promise<string> {
  return (await request(url)).url || url
}
