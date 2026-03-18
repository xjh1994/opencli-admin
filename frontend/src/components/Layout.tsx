import { Outlet, NavLink } from 'react-router-dom'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  Database,
  ListChecks,
  FileText,
  Clock,
  Bell,
  Server,
  ChevronLeft,
  ChevronRight,
  Moon,
  Sun,
  Languages,
} from 'lucide-react'
import { clsx } from 'clsx'

export default function Layout() {
  const { t, i18n } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)
  const [dark, setDark] = useState(false)

  const NAV_ITEMS = [
    { to: '/dashboard',      label: t('nav.dashboard'),     icon: LayoutDashboard },
    { to: '/sources',        label: t('nav.sources'),       icon: Database },
    { to: '/tasks',          label: t('nav.tasks'),         icon: ListChecks },
    { to: '/records',        label: t('nav.records'),       icon: FileText },
    { to: '/schedules',      label: t('nav.schedules'),     icon: Clock },
    { to: '/notifications',  label: t('nav.notifications'), icon: Bell },
    { to: '/workers',        label: t('nav.workers'),       icon: Server },
  ]

  const toggleDark = () => {
    setDark((d) => !d)
    document.documentElement.classList.toggle('dark')
  }

  const toggleLang = () => {
    const next = i18n.language === 'zh' ? 'en' : 'zh'
    i18n.changeLanguage(next)
    localStorage.setItem('lang', next)
  }

  return (
    <div className={clsx('flex h-screen overflow-hidden', dark && 'dark')}>
      {/* Sidebar */}
      <aside
        className={clsx(
          'flex flex-col bg-gray-900 text-white transition-all duration-200',
          collapsed ? 'w-16' : 'w-56'
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-700">
          <span className="text-blue-400 font-bold text-lg">⚡</span>
          {!collapsed && <span className="font-semibold text-sm">OpenCLI Admin</span>}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                )
              }
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Bottom controls */}
        <div className="px-2 py-3 border-t border-gray-700 flex flex-col gap-2">
          {/* Language toggle */}
          <button
            onClick={toggleLang}
            title={i18n.language === 'zh' ? 'Switch to English' : '切换为中文'}
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-400 hover:bg-gray-800 hover:text-white text-sm transition-colors"
          >
            <Languages size={18} />
            {!collapsed && (
              <span className="font-medium">
                {i18n.language === 'zh' ? '中文' : 'English'}
              </span>
            )}
          </button>

          {/* Dark mode toggle */}
          <button
            onClick={toggleDark}
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-400 hover:bg-gray-800 hover:text-white text-sm transition-colors"
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
            {!collapsed && <span>{dark ? t('nav.light') : t('nav.dark')}</span>}
          </button>

          {/* Collapse toggle */}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-400 hover:bg-gray-800 hover:text-white text-sm transition-colors"
          >
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            {!collapsed && <span>{t('nav.collapse')}</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
