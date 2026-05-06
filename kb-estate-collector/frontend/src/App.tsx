import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import AppShell from "@/components/layout/AppShell"
import DashboardPage from "@/pages/DashboardPage"
import ComplexListPage from "@/pages/complexes/ComplexListPage"
import ComplexDetailPage from "@/pages/complexes/ComplexDetailPage"
import BatchSettingsPage from "@/pages/batches/BatchSettingsPage"
import RunListPage from "@/pages/runs/RunListPage"
import RunDetailPage from "@/pages/runs/RunDetailPage"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Toaster position="top-right" richColors />
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="complexes" element={<ComplexListPage />} />
            <Route path="complexes/:id" element={<ComplexDetailPage />} />
            <Route path="batches" element={<BatchSettingsPage />} />
            <Route path="runs" element={<RunListPage />} />
            <Route path="runs/:id" element={<RunDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
