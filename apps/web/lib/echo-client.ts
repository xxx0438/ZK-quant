/**
 * Browser-side Echo API client. Always hits /api/echo/* (the Next.js proxy).
 */

export type ApiError = {
  error: {
    code: string;
    message: string;
    hint?: string;
    request_id?: string;
  };
};

export class EchoApiError extends Error {
  code: string;
  hint?: string;
  status: number;
  constructor(status: number, body: ApiError) {
    super(body.error?.message ?? "Unknown error");
    this.code = body.error?.code ?? "unknown";
    this.hint = body.error?.hint;
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const r = await fetch(`/api/echo${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init.headers || {}),
    },
  });
  const text = await r.text();
  const body = text ? JSON.parse(text) : {};
  if (!r.ok) throw new EchoApiError(r.status, body);
  return body as T;
}

// ─────────── Auth ───────────
export const auth = {
  signup: (email: string, password: string) =>
    request<{ user_id: string; api_key: string; session_token: string }>(
      "/v1/auth/signup",
      { method: "POST", body: JSON.stringify({ email, password }) },
    ),
  login: (email: string, password: string) =>
    request<{ user_id: string; session_token: string }>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  walletNonce: (address: string) =>
    request<{ message: string; nonce: string; issued_at: string }>(
      "/v1/auth/wallet/nonce",
      { method: "POST", body: JSON.stringify({ address }) },
    ),
  walletVerify: (data: {
    address: string;
    signature: string;
    nonce: string;
    issued_at: string;
  }) =>
    request<{ user_id: string; session_token: string; wallet: string }>(
      "/v1/auth/wallet/verify",
      { method: "POST", body: JSON.stringify(data) },
    ),
};

// ─────────── Quant Marketplace ───────────
export type QuantProfile = {
  profile_id: string;
  handle: string;
  revenue_share_bps: number;
  tier: string;
  payout_address: string;
};

export type Submission = {
  id: string;
  model_id: string;
  name: string;
  status: "pending" | "verifying" | "approved" | "rejected" | "pending_human";
  metrics: Record<string, unknown> | null;
  submitted_at: string;
  cert_id: string | null;
};

export type Earnings = {
  handle: string;
  revenue_share_bps: number;
  payout_address: string;
  lifetime_earned_usd: number;
  pending_usd: number;
  settled_usd: number;
  next_settlement: string;
  by_model: Array<{
    model_id: string;
    earned_cents: number;
    calls: number;
  }>;
};

export const quant = {
  register: (body: {
    handle: string;
    display_name: string;
    bio?: string;
    payout_address: string;
  }) => request<QuantProfile>("/v1/quant/register", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  getUploadUrl: (body: { proposed_model_id: string; artifact_type: "artifact" | "kit" }) =>
    request<{ upload_url: string; key: string; expires_in: number }>(
      "/v1/quant/models/upload-url",
      { method: "POST", body: JSON.stringify(body) },
    ),
  submitModel: (body: {
    proposed_model_id: string;
    name: string;
    description?: string;
    category?: string;
    artifact_url: string;
    artifact_sha256: string;
    backtest_kit_url: string;
    backtest_kit_sha256: string;
  }) => request<{ submission_id: string; status: string; message: string }>(
    "/v1/quant/models/submit",
    { method: "POST", body: JSON.stringify(body) },
  ),
  listModels: () =>
    request<{
      submissions: Submission[];
      listed_models: Array<{
        id: string;
        name: string;
        is_listed: boolean;
        price_per_call_cents: number;
        live_sharpe_30d: number | null;
      }>;
    }>("/v1/quant/models"),
  earnings: () => request<Earnings>("/v1/quant/earnings"),
};
