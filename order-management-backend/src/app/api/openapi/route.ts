// === OPENAPI SPEC ENDPOINT ===
// Serves the generated OpenAPI specification

import { OpenApiDocument } from "@/shared/openapi/generator";
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json(OpenApiDocument, {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=3600", // Cache for 1 hour
    },
  });
}
