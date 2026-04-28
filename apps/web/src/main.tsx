import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './lib/i18n'
import App from './App.tsx'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PageLoader } from './components/PageLoader'
import { initWebVitalsLogging, initWebVitalsMonitoring } from './lib/webVitals'
import { initAnalytics } from './lib/analytics'
import { installChunkRecoveryHandlers } from './lib/chunkRecovery'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      refetchOnMount: false,
      retry: 1,
    },
  },
})

initAnalytics()
initWebVitalsMonitoring()
initWebVitalsLogging()
installChunkRecoveryHandlers()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<PageLoader />}>
        <App />
      </Suspense>
    </QueryClientProvider>
  </StrictMode>,
)
