import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StatLine — Ask the game",
  description: "NBA answers grounded in recent game logs.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
