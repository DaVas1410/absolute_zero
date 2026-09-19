import experienciaArquitectura from '../../../data/sample_rfps/rfp_experiencia_arquitectura.txt?raw'
import slaNoRespaldado from '../../../data/sample_rfps/rfp_sla_no_respaldado.txt?raw'
import saasIaMlops from '../../../data/sample_rfps/rfp_saas_ia_mlops.txt?raw'

export interface SampleRfp {
  id: string
  label: string
  text: string
}

// Exactly the real sample files that exist under data/sample_rfps/ - no
// invented example with no backing file.
export const SAMPLE_RFPS: SampleRfp[] = [
  {
    id: 'experiencia_arquitectura',
    label: 'Experiencia + arquitectura (caso feliz)',
    text: experienciaArquitectura.trim(),
  },
  {
    id: 'sla_no_respaldado',
    label: 'SLA no respaldado (caso adversarial)',
    text: slaNoRespaldado.trim(),
  },
  {
    id: 'saas_ia_mlops',
    label: 'MLOps + RAG + SaaS multi-tenant',
    text: saasIaMlops.trim(),
  },
]
