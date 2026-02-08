import { NavLink } from "react-router-dom"
import {
  LayoutDashboard,
  Building2,
  ListChecks,
  History,
  Database,
} from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "대시보드" },
  { to: "/complexes", icon: Building2, label: "단지 관리" },
  { to: "/jobs", icon: ListChecks, label: "수집 작업" },
  { to: "/runs", icon: History, label: "실행 이력" },
  { to: "/data", icon: Database, label: "데이터 탐색" },
]

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <Building2 className="mr-2 h-5 w-5 text-primary" />
        <span className="font-semibold text-sm">KB Estate Collector</span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t p-3 text-xs text-muted-foreground">v0.1.0</div>
    </aside>
  )
}
