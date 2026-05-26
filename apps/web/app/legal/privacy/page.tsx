export const metadata = { title: "Privacy Policy — Echo Protocol" };

export default function Privacy() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12 prose prose-invert">
      <h1>Privacy Policy</h1>
      <p>Last updated: May 26, 2026</p>

      <h2>1. Data we collect</h2>
      <ul>
        <li>Account: email, password hash, wallet address (optional)</li>
        <li>Usage: API call logs, predictions, timestamps, IP address</li>
        <li>Payment: amounts, transaction hashes (Coinbase Commerce charge IDs)</li>
      </ul>

      <h2>2. We do NOT collect</h2>
      <ul>
        <li>Private keys (we never custody)</li>
        <li>Off-platform trading activity</li>
        <li>Browsing data outside echo.ai</li>
      </ul>

      <h2>3. Cookies</h2>
      <p>Session cookies only. No third-party tracking pixels.</p>

      <h2>4. Data retention</h2>
      <p>Account data: until account deletion. API logs: 90 days. Prediction history: 12 months.</p>

      <h2>5. Your rights</h2>
      <p>Request export/deletion at privacy@echo.ai. We respond within 30 days.</p>
    </div>
  );
}
