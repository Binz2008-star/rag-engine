import { NextRequest, NextResponse } from "next/server";

// AI benchmark route temporarily disabled due to schema mismatches
// TODO: Fix schema alignment and re-enable
export async function POST(request: NextRequest) {
  return NextResponse.json(
    { error: "AI benchmark temporarily disabled" },
    { status: 503 }
  );
}

// GET /api/admin/ai/benchmark/run/[id] - Get benchmark run results
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  return NextResponse.json(
    { error: "AI benchmark temporarily disabled" },
    { status: 503 }
  );
}
