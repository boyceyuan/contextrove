import { readFile } from "node:fs/promises"
import path from "node:path"

export const contextMarker = "Obsidian memory navigation (on-demand):"

// Client-neutral assembly policy; callers supply approved paths and discovery.
// Read fresh on every request. Never use a session-wide "already loaded" flag.
export async function assembleMemoryContext({ vault, coreNotes, indexNote, directory,
  discoverEntries, system = [], maxEntries = 8 }) {
  const existing = system.filter((part) => part.type === "text" && !part.text.startsWith(contextMarker))
    .map((part) => part.text).join("\n\n")
  const fallback = [], errors = [], reused = []
  for (const relative of coreNotes) {
    try {
      const content = (await readFile(path.join(vault, relative), "utf8")).trim()
      if (!content) throw new Error("EMPTY_NOTE")
      if (existing.includes(content)) reused.push(relative)
      else fallback.push(`## ${relative}\n${content}`)
    } catch (error) {
      errors.push(`${relative}: ${error.code ?? error.message}`)
    }
  }
  let matches = []
  try {
    matches = await discoverEntries(directory)
  } catch (error) {
    errors.push(`Entry discovery: ${error.code ?? error.message}`)
  }
  const entries = matches.slice(0, maxEntries)
  const omitted = matches.length - entries.length
  const text = [contextMarker, `Canonical vault: ${vault}`,
    "Reuse identical current rules. Read canonical project notes on demand; navigation is not evidence of current facts.",
    "Before editing, read the canonical topic, reconcile corrections rather than append competing claims, and read back. No durable delta means no write.",
    `Project index (on demand): ${path.join(vault, indexNote)}`,
    entries.length ? `Candidate notes (path matching does not prove relevance):\n${entries.map((file) => `- ${file}`).join("\n")}` : "No matched project. Locate the task's topic without guessing project identity.",
    omitted ? `${omitted} additional candidates omitted; search within the approved scope when needed.` : "",
    errors.length ? `Read gaps (not absence of memory):\n${errors.join("\n")}` : "",
    ...fallback,
  ].filter(Boolean).join("\n\n")
  return { text, reused, fallbackCount: fallback.length, entries, omitted, errors }
}

export async function injectMemoryContext(event, options) {
  const result = await assembleMemoryContext({ ...options, system: event.system })
  for (let i = event.system.length - 1; i >= 0; i--) {
    if (event.system[i].type === "text" && event.system[i].text.startsWith(contextMarker)) event.system.splice(i, 1)
  }
  event.system.push({ type: "text", text: result.text })
  return result
}
