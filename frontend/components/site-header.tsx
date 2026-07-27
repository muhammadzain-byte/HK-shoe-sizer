"use client";

import Link from "next/link";
import { Camera, ClipboardCheck, LayoutDashboard, LogOut, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scans/new", label: "New scan", icon: Camera },
  { href: "/validation", label: "Validation", icon: ClipboardCheck },
  { href: "/profile", label: "Profile", icon: UserRound },
];

export function SiteHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { logout, user } = useAuth();

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-zinc-200/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-5">
        <Link href="/dashboard" className="flex items-center gap-2 text-lg font-semibold text-ink">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-sage text-sm font-bold text-white">M</span>
          <span className="hidden sm:inline">MirrorStep</span>
        </Link>
        <nav className="flex items-center gap-1" aria-label="Main navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors ${
                  active ? "bg-sage/12 text-sage" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            );
          })}
          <span className="hidden max-w-36 truncate border-l border-zinc-200 pl-3 text-sm text-zinc-500 lg:inline">
            {user?.email}
          </span>
          <button
            className="flex h-10 w-10 items-center justify-center rounded-lg text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-950"
            type="button"
            onClick={handleLogout}
            aria-label="Sign out"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
          </button>
        </nav>
      </div>
    </header>
  );
}
