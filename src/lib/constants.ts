export const CANDIDATE_A_USERNAME = 'charlles.evangelista'
export const CANDIDATE_B_USERNAME = 'delegadasheila'

export const CANDIDATE_A_DISPLAY = 'Charlles Evangelista'
export const CANDIDATE_B_DISPLAY = 'Delegada Sheila'

export const CANDIDATE_A_CARGO = 'Candidato'
export const CANDIDATE_B_CARGO = 'Deputada Estadual'

export const CANDIDATE_A_COLOR = 'var(--color-candidate-a)'
export const CANDIDATE_B_COLOR = 'var(--color-candidate-b)'

export const CANDIDATE_A_COLOR_LIGHT = 'var(--color-candidate-a-light)'
export const CANDIDATE_B_COLOR_LIGHT = 'var(--color-candidate-b-light)'

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export type CandidateFilter = 'charlles' | 'sheila'

export const CANDIDATE_OPTIONS: Array<{ value: CandidateFilter; label: string }> = [
  { value: 'charlles', label: 'Charlles Evangelista' },
  { value: 'sheila', label: 'Delegada Sheila' },
] as const

export const COMPETITOR_USERNAME = 'delegadaione'
export const COMPETITOR_DISPLAY = 'Delegada Ione'

export const NAV_TABS = [
  { label: 'Painel', href: '/overview' },
  { label: 'Termômetro', href: '/sentiment' },
  { label: 'Temas Quentes', href: '/themes' },
  { label: 'Posts', href: '/posts' },
  { label: 'Perfil', href: '/comparison' },
  { label: 'Concorrência', href: '/competitor' },
  { label: 'Estratégia IA', href: '/insights' },
] as const
