import type { ReactElement } from 'react'
import { SkillTriggerProvider } from '../contexts/SkillTriggerContext'

export function TestWrapper({ children }: { children: ReactElement }) {
  return (
    <SkillTriggerProvider>
      {children}
    </SkillTriggerProvider>
  )
}
