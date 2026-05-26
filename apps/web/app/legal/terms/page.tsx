export const metadata = { title: "Terms of Service — Echo Protocol" };

export default function Terms() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12 prose prose-invert">
      <h1>Terms of Service</h1>
      <p>Last updated: May 26, 2026</p>

      <h2>1. Nature of Service</h2>
      <p>
        Echo Protocol provides <strong>quantitative data and analytics APIs</strong>. We do not provide
        investment advice, brokerage, custody, or asset management services to API users. Outputs from
        our APIs are signals, factors, and probabilities — not recommendations to buy or sell.
      </p>

      <h2>2. Not Investment Advice</h2>
      <p>
        Use of Echo's APIs does not establish a fiduciary, advisory, or agent relationship. We do not
        consider any user's specific circumstances. All API outputs are general-purpose quantitative
        information for use at your sole discretion and risk.
      </p>

      <h2>3. No Warranty of Performance</h2>
      <p>
        Past performance metrics (including those in performance certificates) are historical and do
        NOT guarantee future results. Cryptographic certificates verify computational integrity, not
        future profitability.
      </p>

      <h2>4. Eligibility</h2>
      <p>
        You represent that you are: (a) at least 18 years old; (b) acting in a business or
        professional capacity OR as a sophisticated individual investor; (c) not located in
        OFAC-sanctioned jurisdictions.
      </p>

      <h2>5. Limitation of Liability</h2>
      <p>
        TO THE MAXIMUM EXTENT PERMITTED BY LAW, ECHO'S TOTAL LIABILITY IS LIMITED TO THE FEES YOU
        PAID IN THE 12 MONTHS PRIOR TO THE CLAIM. ECHO IS NOT LIABLE FOR ANY TRADING LOSSES,
        OPPORTUNITY COSTS, OR CONSEQUENTIAL DAMAGES.
      </p>

      <h2>6. Echo Capital</h2>
      <p>
        Echo Capital is a separate private investment fund operated by Echo Capital GP, LLC. Public
        dashboards displaying Echo Capital's on-chain activity are for informational purposes ONLY
        and do NOT constitute an offer to sell securities or a solicitation of investment.
      </p>

      <h2>7. Termination</h2>
      <p>We may suspend service at any time. Unused balance is refundable upon written request.</p>

      <h2>8. Governing Law</h2>
      <p>Delaware, United States. Disputes resolved by binding arbitration.</p>

      <p className="text-zinc-500 text-sm mt-12">
        Questions: legal@echo.ai
      </p>
    </div>
  );
}
