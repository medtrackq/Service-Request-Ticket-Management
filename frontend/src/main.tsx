import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import './index.css'
import { ToastProvider } from './components/Toast'
import { Loading } from './components/ui'
import { I18nProvider, useI18n } from './i18n'
import { HomePage } from './portal/HomePage'
import { PortalLayout } from './portal/PortalLayout'
import { PrivacyPage } from './portal/PrivacyPage'
import { RequestFormPage } from './portal/RequestFormPage'
import { SuccessPage } from './portal/SuccessPage'
import { TrackPage } from './portal/TrackPage'
import { TrackTicketPage } from './portal/TrackTicketPage'

const AdminApp = lazy(() => import('./admin/AdminApp'))

function NotFound() {
  const { tr } = useI18n()
  return (
    <div className="card mx-auto mt-10 max-w-md p-8 text-center">
      <p className="text-4xl font-bold text-navy-900">404</p>
      <p className="mt-2 text-slate-600">{tr('ไม่พบหน้าที่ต้องการ', 'Page not found')}</p>
      <Link to="/" className="btn-primary mt-5">
        {tr('กลับหน้าหลัก', 'Back to home')}
      </Link>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route element={<PortalLayout />}>
        <Route index element={<HomePage />} />
        <Route path="request/:slug" element={<RequestFormPage />} />
        <Route path="request/:slug/success" element={<SuccessPage />} />
        <Route path="track" element={<TrackPage />} />
        <Route path="track/:ticketNumber" element={<TrackTicketPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route
        path="admin/*"
        element={
          <Suspense fallback={<Loading />}>
            <AdminApp />
          </Suspense>
        }
      />
    </Routes>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <ToastProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ToastProvider>
    </I18nProvider>
  </StrictMode>,
)
