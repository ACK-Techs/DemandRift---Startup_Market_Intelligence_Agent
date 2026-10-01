import { BackendUnavailable } from "@/components/workspace/backend-unavailable";

export function PainPointsBoard() {
  return <BackendUnavailable title="Problem evidence unavailable" description="Problem findings have not been loaded. Document counts, independent examples and contrary findings require a validated evidence bundle." />;
}
