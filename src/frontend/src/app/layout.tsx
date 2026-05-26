import type { Metadata } from "next";
import { UserProvider } from "@auth0/nextjs-auth0/client";
import QueryProvider from "@/components/ui/QueryProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research Your Doctor",
  description:
    "Healthcare provider intelligence platform. Personal use only. Powered by federal open data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <UserProvider>
          <QueryProvider>{children}</QueryProvider>
        </UserProvider>
      </body>
    </html>
  );
}
