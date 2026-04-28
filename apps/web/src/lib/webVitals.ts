import { onCLS, onINP, onFCP, onLCP, onTTFB, type Metric } from 'web-vitals'
import logger from './logger'
import { trackEvent } from './analytics'

export interface WebVitalsEnv {
  DEV: boolean
  VITE_ENABLE_WEB_VITALS_LOGGING?: string
}

export type WebVitalReporter = (callback: (metric: Metric) => void) => void

interface InitWebVitalsLoggingInput {
  env?: WebVitalsEnv
  reporters?: readonly WebVitalReporter[]
  log?: (...args: unknown[]) => void
}

interface InitWebVitalsMonitoringInput {
  reporters?: readonly WebVitalReporter[]
  track?: (metric: Metric) => void
}

const DEFAULT_REPORTERS: readonly WebVitalReporter[] = [onCLS, onINP, onFCP, onLCP, onTTFB]

export const shouldEnableWebVitalsLogging = (env: WebVitalsEnv): boolean => {
  return env.DEV && env.VITE_ENABLE_WEB_VITALS_LOGGING === 'true'
}

export const formatWebVitalLogArgs = (metric: Metric): [string, string, number, string] => {
  return ['[web-vitals]', metric.name, metric.value, metric.rating]
}

export const formatWebVitalAnalyticsProps = (metric: Metric) => ({
  metric_name: metric.name,
  metric_value: metric.value,
  metric_rating: metric.rating,
  metric_delta: metric.delta,
  navigation_type: metric.navigationType,
})

export function initWebVitalsLogging({
  env = import.meta.env,
  reporters = DEFAULT_REPORTERS,
  log = (...args: unknown[]) => logger.debug(...args),
}: InitWebVitalsLoggingInput = {}): boolean {
  if (!shouldEnableWebVitalsLogging(env)) {
    return false
  }

  reporters.forEach((report) => {
    report((metric: Metric) => {
      log(...formatWebVitalLogArgs(metric))
    })
  })

  return true
}

export function initWebVitalsMonitoring({
  reporters = DEFAULT_REPORTERS,
  track = (metric: Metric) => {
    trackEvent('web_vital', formatWebVitalAnalyticsProps(metric))
  },
}: InitWebVitalsMonitoringInput = {}): true {
  reporters.forEach((report) => {
    report((metric: Metric) => {
      track(metric)
    })
  })

  return true
}
