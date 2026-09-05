import { handleDocentChat } from "@/lib/docent/chat";

// knowledge 스냅샷을 fs로 읽으므로 Node 런타임 필수.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// A-1 framework adapter (T-001) — 로직은 @/lib/docent/chat 에 있다.
export async function POST(request: Request) {
  return handleDocentChat(request);
}
