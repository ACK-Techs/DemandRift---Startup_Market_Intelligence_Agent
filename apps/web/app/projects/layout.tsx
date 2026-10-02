export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  return <><a className="sr-only z-50 rounded-lg bg-[var(--surface)] p-3 text-sm font-semibold text-[var(--ink)] focus:not-sr-only focus:fixed focus:left-3 focus:top-3" href="#project-content">Skip to project content</a>{children}</>;
}
