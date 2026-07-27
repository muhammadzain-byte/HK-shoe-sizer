import { SiteHeader } from "@/components/site-header";
import { ProtectedRoute } from "@/components/protected-route";

export function DashboardShell({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-porcelain">
        <SiteHeader />
        <main className="mx-auto max-w-6xl px-4 py-7 sm:px-5 sm:py-9">{children}</main>
      </div>
    </ProtectedRoute>
  );
}
