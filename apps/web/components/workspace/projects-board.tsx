import { BackendUnavailable } from "@/components/workspace/backend-unavailable";

export function ProjectsBoard() {
  return <BackendUnavailable title="Projects unavailable" description="The project list has not been loaded from the backend. Saved project IDs and their research history will appear after account and project integration." />;
}
