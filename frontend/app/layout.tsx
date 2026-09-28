import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StatLine — The numbers. The whole story.",
  description:
    "Ask NBA questions, explore player form, and compare recent performances with answers grounded in game logs.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
