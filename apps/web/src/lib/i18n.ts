/**
 * Internationalization (i18n) configuration and initialization.
 *
 * Sets up i18next with React integration for multi-language support.
 * Uses HTTP backend to lazy-load translation files and browser language
 * detection for automatic locale selection.
 *
 * Architecture:
 * - Uses i18next as the core i18n framework
 * - React integration via react-i18next hooks (useTranslation)
 * - HTTP backend loads JSON translation files from /public/locales/
 * - Browser language detection with localStorage persistence
 *
 * Supported Languages:
 * - Chinese (Simplified): 'zh' - Default/fallback language
 * - English: 'en'
 *
 * Translation Namespaces:
 * - common: Shared UI elements, buttons, labels
 * - auth: Login, registration, password reset
 * - dashboard: Dashboard-specific content
 * - editor: Editor interface and controls
 * - chat: AI chat interface
 * - settings: Application settings
 * - home: Landing page content
 * - privacy: Privacy policy
 * - errors: Error messages
 * - project: Project management
 * - versions: Version history
 * - admin: Admin panel
 * - skills: Skills/special abilities
 * - materials: Writing materials/references
 * - onboarding: New user onboarding and persona setup
 *
 * Usage:
 * ```tsx
 * import { useTranslation } from 'react-i18next';
 *
 * function MyComponent() {
 *   const { t, i18n } = useTranslation();
 *   return (
 *     <div>
 *       <h1>{t('welcome')}</h1>
 *       <button onClick={() => i18n.changeLanguage('en')}>
 *         Switch to English
 *       </button>
 *     </div>
 *   );
 * }
 * ```
 *
 * @module lib/i18n
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import Backend from 'i18next-http-backend';

i18n
  // HTTP backend for loading translation files from /public/locales/
  .use(Backend)
  // Automatic language detection from browser/localStorage
  .use(LanguageDetector)
  // React integration for hooks and components
  .use(initReactI18next)
  .init({
    /** Default language when detection fails */
    fallbackLng: 'zh',

    /** Languages with available translations */
    supportedLngs: ['zh', 'en'],

    /**
     * Translation namespaces for organizing content.
     * Each namespace corresponds to a separate JSON file per language.
     */
    ns: ['common', 'auth', 'dashboard', 'editor', 'chat', 'settings', 'home', 'privacy', 'errors', 'project', 'versions', 'admin', 'skills', 'materials', 'points', 'referral', 'onboarding'],

    /** Default namespace when not specified in useTranslation() */
    defaultNS: 'common',

    /** HTTP backend configuration for loading translation files */
    backend: {
      /** Path pattern for translation JSON files */
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },

    /** Language detection configuration */
    detection: {
      /** Detection order: only explicit user preference stored in localStorage */
      order: ['localStorage'],
      /** Cache detected language in localStorage */
      caches: ['localStorage'],
      /** localStorage key for storing language preference */
      lookupLocalStorage: 'zenstory-language',
    },

    /** Interpolation settings */
    interpolation: {
      /** React already escapes values, disable i18next escaping */
      escapeValue: false,
    },

    /** Debug mode - set to true for development to see missing keys */
    debug: false,

    /** React-specific configuration */
    react: {
      /** Use React Suspense for loading translations */
      useSuspense: true,
    },
  });

export default i18n;
