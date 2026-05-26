export default function Disclosures() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12 prose prose-invert">
      <h1>Risk Disclosures</h1>

      <div className="border border-yellow-700 bg-yellow-900/20 p-4 rounded my-6">
        <strong className="text-yellow-300">IMPORTANT:</strong> Trading cryptocurrencies and using
        quantitative signals carries substantial risk of loss. You may lose 100% of capital.
      </div>

      <h2>Echo's Role</h2>
      <ul>
        <li>We provide quantitative data APIs.</li>
        <li>We are NOT a registered investment adviser.</li>
        <li>We are NOT a broker-dealer.</li>
        <li>We do NOT custody user funds.</li>
        <li>We do NOT guarantee returns.</li>
      </ul>

      <h2>Forward Test Limitations</h2>
      <p>
        Live forward test records (e.g., "30-day live Sharpe") reflect past performance only and may
        not predict future results. Market regimes change. Alpha decays.
      </p>

      <h2>Echo Capital Disclosures</h2>
      <p>
        Echo Capital is operated as a private fund. Public on-chain wallet activity is shown for
        transparency. It does NOT constitute a public offering. Investment in Echo Capital is
        restricted to accredited investors and qualified purchasers under applicable securities laws.
      </p>
    </div>
  );
}
