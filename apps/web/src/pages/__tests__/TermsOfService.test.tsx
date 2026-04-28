import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TermsOfService from '../TermsOfService'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { returnObjects?: boolean }) => {
      if (options?.returnObjects) {
        return ['Term A', 'Term B']
      }
      return (
        {
          'terms.title': 'Terms of Service',
          'terms.lastUpdated': 'Updated recently',
          'terms.sections.acceptance.title': 'Acceptance',
          'terms.sections.acceptance.content': 'Acceptance content',
          'terms.sections.description.title': 'Description',
          'terms.sections.description.content': 'Description content',
          'terms.sections.userResponsibilities.title': 'Responsibilities',
          'terms.sections.intellectualProperty.title': 'IP',
          'terms.sections.intellectualProperty.content': 'IP content',
          'terms.sections.aiGeneratedContent.title': 'AI content',
          'terms.sections.aiGeneratedContent.content': 'AI generated content',
          'terms.sections.subscriptionBilling.title': 'Billing',
          'terms.sections.subscriptionBilling.content': 'Billing content',
          'terms.sections.autoRenewalCancellation.title': 'Auto renewal',
          'terms.sections.autoRenewalCancellation.content': 'Renewal content',
          'terms.sections.refundPolicy.title': 'Refunds',
          'terms.sections.refundPolicy.content': 'Refund content',
          'terms.sections.trialAndUpgrade.title': 'Trials',
          'terms.sections.trialAndUpgrade.content': 'Trial content',
          'terms.sections.pricingChangesTaxes.title': 'Pricing changes',
          'terms.sections.pricingChangesTaxes.content': 'Pricing content',
          'terms.sections.termination.title': 'Termination',
          'terms.sections.termination.content': 'Termination content',
          'terms.sections.disclaimer.title': 'Disclaimer',
          'terms.sections.disclaimer.content': 'Disclaimer content',
          'terms.sections.limitation.title': 'Limitation',
          'terms.sections.limitation.content': 'Limitation content',
          'terms.sections.indemnification.title': 'Indemnification',
          'terms.sections.indemnification.content': 'Indemnification content',
          'terms.sections.governingLaw.title': 'Governing law',
          'terms.sections.governingLaw.content': 'Governing law content',
          'terms.sections.changes.title': 'Changes',
          'terms.sections.changes.content': 'Changes content',
          'terms.sections.contact.title': 'Contact',
          'terms.sections.contact.content': 'Contact content',
        } as Record<string, string>
      )[key] ?? key
    },
  }),
}))

vi.mock('../../components/PublicHeader', () => ({
  PublicHeader: () => <div>PublicHeader</div>,
}))

describe('TermsOfService', () => {
  beforeEach(() => {
    vi.stubGlobal('scrollTo', vi.fn())
  })

  it('renders terms sections and scrolls to the top on load', () => {
    render(<TermsOfService />)

    expect(screen.getByText('Terms of Service')).toBeInTheDocument()
    expect(screen.getByText('Acceptance')).toBeInTheDocument()
    expect(screen.getByText('AI content')).toBeInTheDocument()
    expect(screen.getByText('Contact')).toBeInTheDocument()
    expect(screen.getAllByText('Term A').length).toBeGreaterThan(0)
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0)
  })
})
