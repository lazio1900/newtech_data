import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import AppShell from "@/components/layout/AppShell"
import DashboardPage from "@/pages/DashboardPage"
import ComplexListPage from "@/pages/complexes/ComplexListPage"
import ComplexDetailPage from "@/pages/complexes/ComplexDetailPage"
import JobListPage from "@/pages/jobs/JobListPage"
import JobDetailPage from "@/pages/jobs/JobDetailPage"
import RunListPage from "@/pages/runs/RunListPage"
import RunDetailPage from "@/pages/runs/RunDetailPage"
import DataExplorerPage from "@/pages/data/DataExplorerPage"

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
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="complexes" element={<ComplexListPage />} />
            <Route path="complexes/:id" element={<ComplexDetailPage />} />
            <Route path="jobs" element={<JobListPage />} />
            <Route path="jobs/:id" element={<JobDetailPage />} />
            <Route path="runs" element={<RunListPage />} />
            <Route path="runs/:id" element={<RunDetailPage />} />
            <Route path="data" element={<DataExplorerPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
