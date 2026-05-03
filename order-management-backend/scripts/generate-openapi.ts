// === OPENAPI GENERATOR ===
// Generates OpenAPI spec from source-of-truth (Zod schemas)

import { writeFileSync } from "fs";
import { OpenApiDocument } from "../src/shared/openapi/generator";

const OUTPUT_FILE = "generated-openapi.json";

async function main() {
  console.log("Generating OpenAPI spec from source-of-truth (Zod schemas)...");

  try {
    // Generate OpenAPI spec from source-of-truth
    const openApiSpec = OpenApiDocument;

    // Write to file
    writeFileSync(OUTPUT_FILE, JSON.stringify(openApiSpec, null, 2) + "\n", "utf8");

    console.log(`OpenAPI spec generated: ${OUTPUT_FILE}`);
    console.log(`Size: ${JSON.stringify(openApiSpec).length} characters`);
    console.log("Source: Zod schemas (source-of-truth)");

  } catch (error) {
    console.error("Failed to generate OpenAPI spec:", error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch((error) => {
    console.error("OpenAPI generation failed:", error);
    process.exit(1);
  });
}

export { main as generateOpenAPI };
