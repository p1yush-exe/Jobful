import type { Metadata } from "next";
import { Cormorant_Garamond, DM_Mono, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

import { AuthProvider } from "@/context/auth-context";
import { JobTrackerProvider } from "@/context/job-tracker-context";

const mono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});

const serif = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Jobful",
  description: "Search, organize, and track job applications in one calm workspace.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${mono.variable} ${sans.variable} ${serif.variable}`}>
      <body>
        <AuthProvider>
          <JobTrackerProvider>{children}</JobTrackerProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
