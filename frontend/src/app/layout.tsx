import './globals.css';
import { ReactNode } from 'react';

export const metadata = {
  title: 'GitHub MCP Productivity Engine',
  description: 'DORA metrics and insights dashboard',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
