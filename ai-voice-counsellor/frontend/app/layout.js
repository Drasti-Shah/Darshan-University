import "./globals.css";

export const metadata = {
  title: "Darshan University — AI Voice Counsellor",
  description: "Admin console for the AI admission counselling voice agent",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
