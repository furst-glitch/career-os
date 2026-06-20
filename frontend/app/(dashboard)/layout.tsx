import { ClientShell } from "@/components/ClientShell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ClientShell>{children}</ClientShell>;
}
