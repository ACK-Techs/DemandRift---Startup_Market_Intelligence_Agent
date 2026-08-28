import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DemandRift | Evidence-backed startup decisions",
  description: "A research workspace for clearer startup validation decisions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
