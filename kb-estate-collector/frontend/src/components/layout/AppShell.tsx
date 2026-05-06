import { Outlet } from "react-router-dom"
import Sidebar from "./Sidebar"

export default function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-background p-6">
        <Outlet />
      </main>
    </div>
  )
}
