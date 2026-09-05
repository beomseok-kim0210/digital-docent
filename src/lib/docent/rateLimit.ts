import { docentConfig } from "@/data/docent";

// 나이브 IP별 레이트리미터.
// 주의: Vercel 서버리스에서는 Lambda 인스턴스별로 Map이 분리되고 콜드스타트 시
// 리셋된다. 어디까지나 속도 제한용 완충 장치이며, 실질적인 비용 방어선은
// Anthropic Console의 워크스페이스 지출 상한이다.
const hits = new Map<string, number[]>();
const MAX_TRACKED_IPS = 500;

export function checkRateLimit(ip: string): { ok: boolean; retryAfterSec?: number } {
  const { windowMs, maxRequests } = docentConfig.rateLimit;
  const now = Date.now();
  const windowStart = now - windowMs;

  const timestamps = (hits.get(ip) ?? []).filter((t) => t > windowStart);

  if (timestamps.length >= maxRequests) {
    const oldest = timestamps[0];
    return { ok: false, retryAfterSec: Math.ceil((oldest + windowMs - now) / 1000) };
  }

  timestamps.push(now);
  hits.set(ip, timestamps);

  if (hits.size > MAX_TRACKED_IPS) {
    const firstKey = hits.keys().next().value;
    if (firstKey !== undefined) hits.delete(firstKey);
  }

  return { ok: true };
}

export function clientIpFrom(headers: Headers): string {
  const forwarded = headers.get("x-forwarded-for");
  return forwarded?.split(",")[0]?.trim() || "unknown";
}
