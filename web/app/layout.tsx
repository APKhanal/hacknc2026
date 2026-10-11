import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pocketwatch — Your workspace",
  applicationName: "Pocketwatch",
  icons: { icon: { url: "/images/pocketwatch-logo.png", type: "image/png", sizes: "500x500" } },
  description: "A little clarity for your next financial decision.",
};
export const viewport: Viewport = { themeColor: "#d7f2fb", colorScheme: "light" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Extensions like Grammarly add attributes to <body> before hydration.
  return <html lang="en"><body suppressHydrationWarning>{children}</body></html>;
}
