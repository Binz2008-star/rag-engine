import type { Metadata } from "next";
import "./globals.css";

// Validate production environment on startup (single entry point)
import "../server/lib/startup";

export const metadata: Metadata = {
  title: "Order Management Backend",
  description: "Operational order management backend with health, auth, seller, and public API routes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      style={
        {
          "--font-geist-sans": "Arial, Helvetica, sans-serif",
          "--font-geist-mono": '"Courier New", Courier, monospace',
        } as React.CSSProperties
      }
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
