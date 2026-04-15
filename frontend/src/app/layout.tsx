import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Risk Monitoring Dashboard",
  description:
    "Portfolio risk metrics for S&P 500, Société Générale, and Siemens",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
