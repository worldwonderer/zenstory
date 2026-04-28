import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { PublicHeader } from '../components/PublicHeader';

export default function TermsOfService() {
  const { t } = useTranslation('privacy');

  // 页面加载时滚动到顶部
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="min-h-screen bg-[hsl(var(--bg-primary))] flex flex-col">
      <PublicHeader variant="home" maxWidth="max-w-6xl" />
      
      <main className="flex-1 max-w-4xl mx-auto px-4 py-12">
        <div className="bg-[hsl(var(--bg-secondary))] rounded-2xl shadow-xl p-8 md:p-12">
          {/* Header */}
          <div className="mb-12 pb-6 border-b border-[hsl(var(--border-color))]">
            <h1 className="text-4xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.title')}
            </h1>
            <p className="text-[hsl(var(--text-secondary))] text-sm">
              {t('terms.lastUpdated')}
            </p>
          </div>

          {/* Acceptance */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.acceptance.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.acceptance.content')}
              </p>
            </div>
          </section>

          {/* Description */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.description.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.description.content')}
              </p>
            </div>
          </section>

          {/* User Responsibilities */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.userResponsibilities.title')}
            </h2>
            <div className="pl-4">
              <ul className="space-y-2">
                {(t('terms.sections.userResponsibilities.items', { returnObjects: true }) as string[]).map((item: string, index: number) => (
                  <li key={index} className="flex items-start gap-2 text-[hsl(var(--text-primary))]">
                    <span className="text-[hsl(var(--text-secondary))] mt-1">✓</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          {/* Intellectual Property */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.intellectualProperty.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.intellectualProperty.content')}
              </p>
            </div>
          </section>

          {/* AI Generated Content */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.aiGeneratedContent.title')}
            </h2>
            <div className="pl-4">
              <div className="bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-color))] rounded-lg p-4">
                <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                  {t('terms.sections.aiGeneratedContent.content')}
                </p>
              </div>
            </div>
          </section>

          {/* Subscription & Billing */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.subscriptionBilling.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.subscriptionBilling.content')}
              </p>
            </div>
          </section>

          {/* Auto-Renewal & Cancellation */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.autoRenewalCancellation.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.autoRenewalCancellation.content')}
              </p>
            </div>
          </section>

          {/* Refund Policy */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.refundPolicy.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.refundPolicy.content')}
              </p>
            </div>
          </section>

          {/* Free Trial & Upgrade */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.trialAndUpgrade.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.trialAndUpgrade.content')}
              </p>
            </div>
          </section>

          {/* Pricing Changes */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.pricingChangesTaxes.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.pricingChangesTaxes.content')}
              </p>
            </div>
          </section>

          {/* Termination */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.termination.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.termination.content')}
              </p>
            </div>
          </section>

          {/* Disclaimer */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.disclaimer.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.disclaimer.content')}
              </p>
            </div>
          </section>

          {/* Limitation of Liability */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.limitation.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.limitation.content')}
              </p>
            </div>
          </section>

          {/* Indemnification */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.indemnification.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.indemnification.content')}
              </p>
            </div>
          </section>

          {/* Governing Law */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.governingLaw.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.governingLaw.content')}
              </p>
            </div>
          </section>

          {/* Changes */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.changes.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.changes.content')}
              </p>
            </div>
          </section>

          {/* Contact */}
          <section className="mb-8">
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-4">
              {t('terms.sections.contact.title')}
            </h2>
            <div className="pl-4">
              <p className="text-[hsl(var(--text-primary))] leading-relaxed">
                {t('terms.sections.contact.content')}
              </p>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
