import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Counterfactual",
  description: "Replay of a simulated financial decision",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
