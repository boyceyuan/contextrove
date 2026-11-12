import assert from "node:assert/strict"
import test from "node:test"
import { mkdtemp, writeFile, rm } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { assembleMemoryContext, injectMemoryContext, contextMarker } from "./memory-context.mjs"

async function fixture(run) {
  const vault = await mkdtemp(path.join(os.tmpdir(), "contextrove-assembly-"))
  try {
    await writeFile(path.join(vault, "rules.md"), "# Rules\nconfirmed-policy")
    await run({ vault, coreNotes: ["rules.md"], indexNote: "index.md",
      directory: "/synthetic/alpha", discoverEntries: async () => ["alpha.md"] })
  } finally {
    await rm(vault, { recursive: true, force: true })
  }
}

test("deduplicates current rules, retains navigation", () => fixture(async (options) => {
  const result = await assembleMemoryContext({ ...options, system: [{ type: "text", text: "# Rules\nconfirmed-policy" }] })
  assert.equal(result.fallbackCount, 0)
  assert.equal(result.reused.length, 1)
  assert(result.text.includes("alpha.md"))
}))

test("fresh requests restore rules; external corrections are read again", () => fixture(async (options) => {
  assert.equal((await assembleMemoryContext(options)).fallbackCount, 1)
  await writeFile(path.join(options.vault, "rules.md"), "CORRECTED_POLICY")
  const result = await assembleMemoryContext({ ...options, system: [{ type: "text", text: "# Rules\nconfirmed-policy" }] })
  assert(result.text.includes("CORRECTED_POLICY"))
}))

test("repeated injection is idempotent and preserves others", () => fixture(async (options) => {
  const event = { system: [{ type: "text", text: "OTHER_PLUGIN" }] }
  await injectMemoryContext(event, options)
  await injectMemoryContext(event, options)
  assert.equal(event.system.filter((p) => p.text.startsWith(contextMarker)).length, 1)
  assert.equal(event.system[0].text, "OTHER_PLUGIN")
  assert(event.system[1].text.includes("confirmed-policy"))
}))

test("project switching refreshes entries and reports omissions", () => fixture(async (options) => {
  const discoverEntries = async (directory) => directory.endsWith("beta") ? ["beta.md"] : Array.from({ length: 10 }, (_, i) => `alpha-${i}.md`)
  const first = await assembleMemoryContext({ ...options, discoverEntries })
  assert.equal(first.omitted, 2)
  const next = await assembleMemoryContext({ ...options, discoverEntries, directory: "/synthetic/beta" })
  assert.deepEqual(next.entries, ["beta.md"])
  assert(!next.text.includes("alpha-"))
}))

test("read and discovery failures are explicit", () => fixture(async (options) => {
  await rm(path.join(options.vault, "rules.md"))
  const result = await assembleMemoryContext({ ...options, discoverEntries: async () => { throw new Error("unavailable") } })
  assert.equal(result.errors.length, 2)
  assert(result.text.includes("Read gaps"))
}))
