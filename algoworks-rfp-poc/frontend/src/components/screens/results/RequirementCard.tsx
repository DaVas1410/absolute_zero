import { useState } from 'react'
import type { DraftSection, Requirement, VerificationResult } from '../../../api/types'
import { submitFeedback } from '../../../api/client'
import { Badge } from '../../ui/Badge'
import { DraftText } from '../../ui/DraftText'
import { FeedbackBadge } from '../../ui/FeedbackBadge'
import { SimilarityBar } from '../../ui/SimilarityBar'
import { Button } from '../../ui/Button'
import { VerdictBadge } from '../../ui/VerdictBadge'
import './RequirementCard.css'

interface RequirementCardProps {
  requirement: Requirement
  draft: DraftSection | undefined
  verification: VerificationResult | undefined
  citationNumbers: Map<string, number>
  selectedChunkId: string | null
  onSelectChunk: (chunkId: string) => void
  isLast: boolean
}

export function RequirementCard({
  requirement,
  draft,
  verification,
  citationNumbers,
  selectedChunkId,
  onSelectChunk,
  isLast,
}: RequirementCardProps) {
  const [feedback, setFeedback] = useState<boolean | null>(null)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false)

  async function handleFeedback(accepted: boolean) {
    if (isSubmittingFeedback) return
    setIsSubmittingFeedback(true)
    setFeedbackError(null)
    try {
      await submitFeedback(requirement.req_id, accepted)
      setFeedback(accepted)
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : 'No se pudo enviar el feedback.')
    } finally {
      setIsSubmittingFeedback(false)
    }
  }

  return (
    <div className={`td-req-card ${isLast ? '' : 'td-req-card--divider'}`}>
      <div className="td-req-card__head">
        <h2 className="text-h2">{requirement.text}</h2>
        <div className="td-req-card__badges">
          {verification && <VerdictBadge supported={verification.supported} confidence={verification.confidence} />}
          {feedback !== null && <FeedbackBadge accepted={feedback} />}
        </div>
      </div>

      {draft ? (
        <>
          <DraftText
            text={draft.text}
            citationNumbers={citationNumbers}
            selectedChunkId={selectedChunkId}
            onSelectChunk={onSelectChunk}
          />

          {draft.reasoning && (
            <p className="text-caption td-req-card__reasoning">
              Por qué se citó lo citado: {draft.reasoning}
            </p>
          )}

          {draft.citation_similarities.length > 0 && (
            <div className="td-req-card__grounding">
              <p className="text-body-sm td-req-card__grounding-overall">
                Similitud global: <strong>{Math.round(draft.overall_similarity * 100)}%</strong>
              </p>
              {draft.citation_similarities.map((sim) => (
                <SimilarityBar
                  key={sim.chunk_id}
                  label={`Fuente ${citationNumbers.get(sim.chunk_id) ?? sim.chunk_id}`}
                  value={sim.similarity}
                />
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="text-body-sm td-req-card__reasoning">Sin borrador para este requisito.</p>
      )}

      {verification && (
        <div className="td-req-card__verdict">
          <p className="text-body-sm">
            {verification.reasoning}
            {verification.retries_used > 0 && ` (${verification.retries_used} reintento(s) usados)`}
          </p>
          {!verification.supported && verification.issues.length > 0 && (
            <ul className="td-req-card__issues">
              {verification.issues.map((issue) => (
                <li key={issue} className="text-body-sm">
                  {issue}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="td-req-card__feedback">
        <Button weight="secondary" disabled={isSubmittingFeedback} onClick={() => handleFeedback(true)}>
          Aceptar
        </Button>
        <Button weight="ghost" disabled={isSubmittingFeedback} onClick={() => handleFeedback(false)}>
          Rechazar
        </Button>
        {feedbackError && (
          <Badge tone="caution">{feedbackError}</Badge>
        )}
      </div>
    </div>
  )
}
