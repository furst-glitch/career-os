"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { CompletenessScore } from "@/components/CompletenessScore";
import { cn } from "@/lib/utils";
import { apiGet, apiPost } from "@/lib/api";

interface Notification {
  id: string; title: string; body: string; is_read: boolean; created_at: string; event_type: string;
}

const NAV = [
  {
    label: "Dashboard",
    href: "/dashboard",
    exact: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
        <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
      </svg>
    ),
  },
  {
    label: "CV Upload",
    href: "/cv",
    exact: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
    ),
  },
  {
    label: "Interview",
    href: "/cv/interview",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    label: "Profil",
    href: "/cv/profile",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  {
    label: "Master CV",
    href: "/cv/master",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    label: "Jobs",
    href: "/jobs",
    exact: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
      </svg>
    ),
  },
  {
    label: "Ledige Jobs",
    href: "/jobs/discovery",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
    ),
  },
  {
    label: "Indsæt jobopslag",
    href: "/jobs/paste",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
        <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
        <line x1="12" y1="11" x2="12" y2="17"/>
        <line x1="9" y1="14" x2="15" y2="14"/>
      </svg>
    ),
  },
  {
    label: "Ansøgninger",
    href: "/applications",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    ),
  },
  {
    label: "Arbejdsgraf",
    href: "/experience",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="6" height="6" rx="1"/><rect x="16" y="3" width="6" height="6" rx="1"/>
        <rect x="9" y="15" width="6" height="6" rx="1"/>
        <line x1="5" y1="9" x2="5" y2="12"/><line x1="19" y1="9" x2="19" y2="12"/>
        <line x1="5" y1="12" x2="12" y2="12"/><line x1="19" y1="12" x2="12" y2="12"/>
        <line x1="12" y1="12" x2="12" y2="15"/>
      </svg>
    ),
  },
  {
    label: "Career Coach",
    href: "/career-coach",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
        <path d="M12 8v4l3 3"/>
      </svg>
    ),
  },
  {
    label: "Career Memory",
    href: "/memory",
    hidden: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
        <path d="M12 6v6l4 2"/>
      </svg>
    ),
  },
  {
    label: "Indstillinger",
    href: "/settings",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    ),
  },
];

function fmtDate(iso: string) {
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (diff === 0) return "I dag";
  if (diff === 1) return "I går";
  if (diff < 7) return `${diff}d`;
  return d.toLocaleDateString("da-DK", { day: "numeric", month: "short" });
}

// ── Notification Bell ─────────────────────────────────────────────────────────

export function NotificationBell({ dropUp = false }: { dropUp?: boolean }) {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function fetchCount() {
      apiGet<{ count: number }>("/notifications/count")
        .then(r => setCount(r.count))
        .catch(() => {});
    }
    fetchCount();
    const t = setInterval(fetchCount, 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    apiGet<{ notifications: Notification[] }>("/notifications?limit=10")
      .then(r => setNotifications(r.notifications ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open]);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  async function markRead(id: string) {
    await apiPost(`/notifications/${id}/read`, {});
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setCount(prev => Math.max(0, prev - 1));
  }

  async function markAllRead() {
    await apiPost("/notifications/read-all", {});
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setCount(0);
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(o => !o)}
        className="relative flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
        aria-label="Notifikationer"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[9px] font-bold text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className={cn(
          "absolute z-50 w-80 rounded-xl border border-slate-700 bg-slate-800 shadow-xl",
          dropUp ? "bottom-10 left-0" : "top-10 right-0"
        )}>
          <div className="flex items-center justify-between border-b border-slate-700 px-4 py-2.5">
            <span className="text-sm font-semibold text-white">Notifikationer</span>
            {count > 0 && (
              <button onClick={markAllRead} className="text-xs text-blue-400 hover:text-blue-300">
                Marker alle læst
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <p className="px-4 py-6 text-center text-xs text-slate-400">Henter...</p>
            ) : notifications.length === 0 ? (
              <p className="px-4 py-6 text-center text-xs text-slate-400">Ingen notifikationer</p>
            ) : (
              notifications.map(n => (
                <button
                  key={n.id}
                  onClick={() => !n.is_read && markRead(n.id)}
                  className={cn(
                    "w-full border-b border-slate-700 px-4 py-3 text-left transition-colors last:border-0",
                    n.is_read ? "opacity-60 hover:bg-slate-750" : "hover:bg-slate-700"
                  )}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && (
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                    )}
                    <div className={cn("min-w-0", n.is_read && "ml-3.5")}>
                      <p className="text-xs font-semibold text-slate-200 leading-tight">{n.title}</p>
                      {n.body && (
                        <p className="mt-0.5 text-xs text-slate-400 line-clamp-2">{n.body}</p>
                      )}
                      <p className="mt-1 text-[10px] text-slate-500">{fmtDate(n.created_at)}</p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
          <div className="border-t border-slate-700 px-4 py-2">
            <Link
              href="/dashboard"
              onClick={() => setOpen(false)}
              className="block text-center text-xs text-blue-400 hover:text-blue-300"
            >
              Se alle i Dashboard →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setUserEmail(data.user?.email ?? null);
    });
  }, []);

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <aside
      className={cn(
        // Mobile: fixed drawer that slides in/out
        "fixed inset-y-0 left-0 z-50 flex h-full w-72 flex-col bg-slate-900 text-white",
        "transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "-translate-x-full",
        // Desktop: static sidebar, always visible
        "lg:relative lg:w-64 lg:translate-x-0 lg:z-auto lg:shrink-0"
      )}
    >
      {/* Logo */}
      <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-bold text-white">CareerOS</span>
        </div>
        {/* Close button — only shown on mobile */}
        <button
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors lg:hidden"
          aria-label="Luk menu"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        {NAV.filter((item) => !item.hidden).map((item) => {
          const isActive = item.exact
            ? pathname === item.href
            : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Completeness Score */}
      <div className="border-t border-slate-800 px-4 py-4">
        <CompletenessScore compact={false} refreshKey={pathname} />
      </div>

      {/* User + notification bell */}
      <div className="border-t border-slate-800 px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs text-slate-400">{userEmail ?? "..."}</p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <NotificationBell dropUp />
            <button
              onClick={handleLogout}
              className="rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-800 hover:text-slate-300"
            >
              Log ud
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
