import Image from "next/image";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return <Image alt="DemandRift" className="h-auto w-auto object-contain" height={compact ? 32 : 40} priority src="/brand/demandrift-logo.png" width={compact ? 118 : 168} />;
}
