import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SEOHelmet } from '../Helmet'

const mockSeoConfig = {
  title: 'SEO Title',
  description: 'SEO description',
  keywords: ['novel', 'writing'],
  canonical: 'https://zenstory.ai/page',
  noindex: false,
  og: {
    type: 'website',
    title: 'OG Title',
    description: 'OG description',
    image: 'https://zenstory.ai/og.png',
  },
  schema: {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: 'SEO Title',
  },
}

let currentLanguage = 'en-US'

vi.mock('react-helmet-async', () => ({
  Helmet: ({
    children,
    htmlAttributes,
  }: {
    children?: React.ReactNode
    htmlAttributes?: { lang?: string }
  }) => (
    <div data-testid="helmet-root" data-lang={htmlAttributes?.lang}>
      {children}
    </div>
  ),
}))

vi.mock('../../providers/SEOProvider', () => ({
  useSEO: () => ({
    seoConfig: mockSeoConfig,
  }),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: {
      language: currentLanguage,
    },
  }),
}))

vi.mock('../../lib/utils', () => ({
  getBaseUrl: () => 'https://zenstory.ai',
}))

describe('SEOHelmet', () => {
  beforeEach(() => {
    currentLanguage = 'en-US'
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        pathname: '/docs/getting-started',
      },
    })
    mockSeoConfig.noindex = false
  })

  it('renders canonical, hreflang, open graph, and schema metadata for public pages', () => {
    render(<SEOHelmet />)

    expect(screen.getByTestId('helmet-root')).toHaveAttribute('data-lang', 'en-US')
    expect(document.querySelector('title')?.textContent).toBe('SEO Title')
    expect(document.querySelector('meta[name="description"]'))?.toHaveAttribute('content', 'SEO description')
    expect(document.querySelector('meta[name="keywords"]'))?.toHaveAttribute('content', 'novel, writing')
    expect(document.querySelector('link[rel="canonical"]'))?.toHaveAttribute('href', 'https://zenstory.ai/page')
    expect(document.querySelectorAll('link[rel="alternate"]')).toHaveLength(3)
    expect(document.querySelector('meta[property="og:title"]'))?.toHaveAttribute('content', 'OG Title')
    expect(document.querySelector('script[type="application/ld+json"]')?.textContent).toContain('"@type":"WebPage"')
  })

  it('renders noindex pages without hreflang links', () => {
    mockSeoConfig.noindex = true
    currentLanguage = 'zh-CN'

    render(<SEOHelmet />)

    expect(screen.getByTestId('helmet-root')).toHaveAttribute('data-lang', 'zh-CN')
    expect(document.querySelector('meta[name="robots"]'))?.toHaveAttribute('content', 'noindex')
    expect(document.querySelectorAll('link[rel="alternate"]')).toHaveLength(0)
  })
})
