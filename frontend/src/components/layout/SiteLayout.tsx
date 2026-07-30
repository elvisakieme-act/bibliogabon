import type React from "react";

import { Footer } from "@/components/layout/Footer";
import { Navbar } from "@/components/layout/Navbar";

export function SiteLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-screen flex-col bg-background text-foreground"><Navbar />{children}<Footer /></div>;
}
