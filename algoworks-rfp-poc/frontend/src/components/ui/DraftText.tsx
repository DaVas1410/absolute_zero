import { Fragment } from 'react'
import { parseCitationMarkers } from '../../utils/citations'
import { Citation } from './Citation'

interface DraftTextProps {
  text: string
  /** chunk_id -> its stable citation number within this requirement's own source list. */
  citationNumbers: Map<string, number>
  selectedChunkId: string | null
  onSelectChunk: (chunkId: string) => void
}

/** Renders draft text, replacing each [[chunk_id]] marker with a Citation component. */
export function DraftText({ text, citationNumbers, selectedChunkId, onSelectChunk }: DraftTextProps) {
  const tokens = parseCitationMarkers(text)

  return (
    <p className="text-body">
      {tokens.map((token, index) => {
        if (token.kind === 'text') {
          return <Fragment key={index}>{token.value}</Fragment>
        }
        const number = citationNumbers.get(token.chunkId)
        if (number === undefined) {
          return null
        }
        return (
          <Citation
            key={index}
            number={number}
            isSelected={selectedChunkId === token.chunkId}
            onClick={() => onSelectChunk(token.chunkId)}
          />
        )
      })}
    </p>
  )
}
