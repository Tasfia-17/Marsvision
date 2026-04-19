import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MarsVision — Mission Control",
  description: "Autonomous Mars rover · Seedream 5.0 · Seedance 2.0 · Seed 2.0",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="font-mono" suppressHydrationWarning>
      <body className="bg-stone-950 text-amber-100 antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
