import { BackendUnavailable } from "@/components/workspace/backend-unavailable";

export function EvidenceLibrary() {
  return <BackendUnavailable title="Evidence unavailable" description="Evidence has not been loaded for a saved research record. Each retained claim requires its source URL, exact quote, capture date, offsets, content hash and normalization version." />;
}
