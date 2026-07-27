import { DashboardShell } from "@/components/dashboard-shell";

export default function AuthenticatedLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <DashboardShell>{children}</DashboardShell>;
}

