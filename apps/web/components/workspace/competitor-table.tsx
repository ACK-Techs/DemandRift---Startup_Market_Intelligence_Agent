import { BackendUnavailable } from "@/components/workspace/backend-unavailable";

export function CompetitorTable() {
  return <BackendUnavailable title="Competitor evidence unavailable" description="Competitor claims and pricing have not been loaded. Official product claims and customer experiences are shown separately when source citations are available." />;
}
