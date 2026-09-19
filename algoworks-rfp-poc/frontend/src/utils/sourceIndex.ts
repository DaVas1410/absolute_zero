import type { PipelineResult, RetrievedChunk } from '../api/types'

export interface SourceIndexEntry {
  chunkId: string
  chunk: RetrievedChunk
  /** Stable citation number, by first appearance across all requirements. */
  number: number
  /** req_ids whose draft actually cites this chunk (may be empty - retrieved but unused). */
  citingReqIds: string[]
}

/**
 * Builds one global, order-stable index of every unique chunk_id retrieved
 * across the whole PipelineResult. Citation numbers are computed globally
 * (not per-requirement) so a chunk's inline citation number in any draft
 * matches its number in the shared source list, since the API has no
 * separate concept of "this section's own source list" beyond `retrieved`.
 */
export function buildSourceIndex(result: PipelineResult): SourceIndexEntry[] {
  const entries: SourceIndexEntry[] = []
  const indexByChunkId = new Map<string, number>()

  for (const requirement of result.requirements) {
    const retrievedChunks = result.retrieved[requirement.req_id] ?? []
    for (const chunk of retrievedChunks) {
      if (indexByChunkId.has(chunk.chunk_id)) continue
      indexByChunkId.set(chunk.chunk_id, entries.length)
      entries.push({ chunkId: chunk.chunk_id, chunk, number: entries.length + 1, citingReqIds: [] })
    }
  }

  for (const requirement of result.requirements) {
    const draft = result.drafts[requirement.req_id]
    if (!draft) continue
    for (const chunkId of draft.cited_chunks) {
      const entryIndex = indexByChunkId.get(chunkId)
      if (entryIndex === undefined) continue
      entries[entryIndex].citingReqIds.push(requirement.req_id)
    }
  }

  return entries
}

export function citationNumberMap(entries: SourceIndexEntry[]): Map<string, number> {
  return new Map(entries.map((entry) => [entry.chunkId, entry.number]))
}
