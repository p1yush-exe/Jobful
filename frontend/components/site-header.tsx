"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/context/auth-context";
import { useJobTracker } from "@/context/job-tracker-context";
import { logout } from "@/services/auth";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/onboarding", label: "Profile" },
];

export function SiteHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { session, clearSession } = useAuth();
  const { overview, loading } = useJobTracker();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const notifications = overview?.notifications ?? [];
  const hasUpdates = notifications.length > 0;

  async function handleLogout() {
    if (session) {
      try {
        await logout({ refresh_token: session.refresh_token });
      } catch {
        // clear locally even if backend fails
      }
      clearSession();
    }
    router.push("/login");
  }

  return (
    <header className="sticky top-4 z-40 px-4 sm:px-6">
      <div className="ui-wrap">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between rounded-full bg-[rgba(251,250,246,0.82)] px-3 py-3 shadow-[0_18px_40px_rgba(52,61,46,0.08)] backdrop-blur-2xl">
          <div className="flex items-center gap-2">
            <Link href="/" className="rounded-full bg-[rgba(47,90,65,0.08)] px-4 py-2 font-semibold tracking-[-0.03em] text-[var(--text)]">
              Jobful
            </Link>
            <nav className="hidden items-center gap-1 md:flex">
              {NAV.map(({ href, label }) => {
                const active = pathname === href || (href !== "/" && pathname.startsWith(href));
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`rounded-full px-4 py-2 text-sm transition duration-700 ease-[cubic-bezier(0.32,0.72,0,1)] ${
                      active
                        ? "bg-white font-medium text-[var(--text)] shadow-[0_4px_12px_rgba(52,61,46,0.06)]"
                        : "text-[var(--text-soft)] hover:bg-white hover:text-[var(--text)]"
                    }`}
                  >
                    {label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {session ? (
              <span className="hidden rounded-full bg-white px-4 py-2 text-sm text-[var(--text-soft)] shadow-[inset_0_0_0_1px_rgba(86,102,74,0.08)] sm:block">
                {session.user.email.toLowerCase()}
              </span>
            ) : null}
            {session ? (
              <div className="relative">
                <button
                  type="button"
                  aria-label="Notifications"
                  aria-expanded={notificationsOpen}
                  onClick={() => setNotificationsOpen((open) => !open)}
                  className="ui-icon-button"
                >
                  <span className="text-base">Alerts</span>
                  {hasUpdates ? <span className="ui-notification-dot" /> : null}
                </button>

                {notificationsOpen ? (
                  <div className="ui-popover right-0 top-[calc(100%+0.8rem)] w-[min(26rem,calc(100vw-2rem))] p-4">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="ui-kicker">Hiring watch</p>
                          <h3 className="mt-2 text-lg font-semibold">Tracked job updates</h3>
                        </div>
                        <span className={`ui-status ${hasUpdates ? "ui-status-red" : "ui-status-green"}`}>
                          {loading ? "Syncing" : `${notifications.length} update${notifications.length === 1 ? "" : "s"}`}
                        </span>
                      </div>

                      {notifications.length === 0 ? (
                        <div className="ui-empty">
                          <p className="text-sm text-[var(--text-soft)]">No hiring closures detected in your tracked jobs.</p>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {notifications.slice(0, 6).map((notification) => (
                            <div key={notification.application_id} className="ui-panel p-4">
                              <div className="flex items-start justify-between gap-3">
                                <div className="space-y-2">
                                  <p className="text-sm font-semibold">{notification.title}</p>
                                  <p className="text-xs text-[var(--text-dim)]">{notification.company}</p>
                                  <p className="text-sm leading-6 text-[var(--text-soft)]">{notification.message}</p>
                                </div>
                                <span className={`ui-status ${notification.can_remove ? "ui-status-yellow" : "ui-status-red"}`}>
                                  {notification.status}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
            <button onClick={() => void handleLogout()} className="ui-button ui-button-secondary px-4 py-2 text-[0.72rem]" type="button">
              Log out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
