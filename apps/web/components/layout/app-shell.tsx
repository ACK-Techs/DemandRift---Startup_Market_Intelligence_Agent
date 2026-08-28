import { AppSidebar } from "@/components/layout/app-sidebar";
import { TopBar } from "@/components/layout/top-bar";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className="flex min-h-dvh"><AppSidebar /><div className="min-w-0 flex-1"><TopBar /><main className="mx-auto w-full max-w-[1600px] px-5 py-7 sm:px-8 sm:py-9 lg:px-10">{children}</main></div></div>;
}
