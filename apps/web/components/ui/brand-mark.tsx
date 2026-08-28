import Image from "next/image";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  const height = compact ? 32 : 40;
  const width = compact ? 118 : 168;
  return <span className="relative block" style={{ height, width }}><Image alt="DemandRift" className="brand-mark-light h-auto w-auto object-contain" fill priority sizes={`${width}px`} src="/brand/demandrift-logo-light-v2.png" /><Image alt="" aria-hidden="true" className="brand-mark-dark h-auto w-auto object-contain" fill priority sizes={`${width}px`} src="/brand/demandrift-logo-dark-v3.png" /></span>;
}
