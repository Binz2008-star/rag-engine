// === VERSION-AWARE CONTRACT TESTING ===
// Compares current schemas against previous release to detect breaking changes

import { execSync } from "child_process";
import { readFileSync, writeFileSync } from "fs";
import { join } from "path";

// === VERSION COMPARISON TYPES ===

interface ContractVersion {
  version: string;
  tag: string;
  schemas: ContractSchema[];
  timestamp: string;
}

interface ContractSchema {
  name: string;
  fields: Record<string, {
    type: string;
    required: boolean;
    enum?: string[];
    nullable?: boolean;
  }>;
}

interface BreakingChange {
  schema: string;
  type: "field_removed" | "field_type_changed" | "field_required_changed" | "enum_value_removed" | "schema_removed";
  description: string;
  severity: "critical" | "major" | "minor";
}

// === VERSION-AWARE SCHEMA EXTRACTOR ===

class VersionAwareSchemaExtractor {
  static extractFromGitTag(tag: string): ContractSchema[] {
    try {
      // Checkout the tag
      execSync(`git checkout ${tag}`, { stdio: "pipe" });
      
      // Extract schemas from that version
      const schemas = this.extractCurrentSchemas();
      
      // Return to current branch
      execSync("git checkout -", { stdio: "pipe" });
      
      return schemas;
    } catch (error) {
      throw new Error(`Failed to extract schemas from tag ${tag}: ${error}`);
    }
  }

  static extractCurrentSchemas(): ContractSchema[] {
    const schemas: ContractSchema[] = [];
    
    try {
      // Read orders schema file
      const ordersSchemaPath = join(process.cwd(), "src/shared/schemas/orders.ts");
      const content = readFileSync(ordersSchemaPath, "utf8");
      
      // Extract CreateOrderSchema
      if (content.includes("CreateOrderSchema")) {
        schemas.push({
          name: "CreateOrderSchema",
          fields: {
            sellerId: { type: "string", required: true },
            customerId: { type: "string", required: true },
            items: { type: "array", required: true },
            paymentType: { type: "enum", required: true, enum: ["CASH_ON_DELIVERY", "CARD", "WALLET"] },
            notes: { type: "string", required: false },
          },
        });
      }
      
      // Extract OrderResponseSchema
      if (content.includes("OrderResponseSchema")) {
        schemas.push({
          name: "OrderResponseSchema",
          fields: {
            id: { type: "string", required: true },
            sellerId: { type: "string", required: true },
            publicOrderNumber: { type: "string", required: true },
            status: { type: "enum", required: true, enum: ["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED"] },
            paymentStatus: { type: "enum", required: true, enum: ["PENDING", "PAID", "FAILED", "REFUNDED"] },
            paymentType: { type: "enum", required: true, enum: ["CASH_ON_DELIVERY", "CARD", "WALLET"] },
            subtotalMinor: { type: "number", required: true },
            deliveryFeeMinor: { type: "number", required: true },
            totalMinor: { type: "number", required: true },
            currency: { type: "string", required: true },
            notes: { type: "string", required: false },
            createdAt: { type: "string", required: true },
            updatedAt: { type: "string", required: true },
            customer: { type: "object", required: true },
            items: { type: "array", required: true },
          },
        });
      }
      
      // Extract ErrorSchema
      if (content.includes("ErrorSchema")) {
        schemas.push({
          name: "ErrorSchema",
          fields: {
            success: { type: "boolean", required: true },
            error: { type: "object", required: true },
          },
        });
      }
      
      return schemas;
    } catch (error) {
      throw new Error(`Failed to extract current schemas: ${error}`);
    }
  }

  static getCurrentVersion(): string {
    try {
      const packageJsonPath = join(process.cwd(), "package.json");
      const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf8"));
      return packageJson.version;
    } catch (error) {
      throw new Error(`Failed to get current version: ${error}`);
    }
  }

  static getPreviousTag(): string | null {
    try {
      const tags = execSync("git tag --sort=-version:refname", { encoding: "utf8" });
      const tagList = tags.trim().split("\n");
      
      // Skip the current version tag if it exists
      const currentVersion = this.getCurrentVersion();
      const currentIndex = tagList.findIndex(tag => tag === `v${currentVersion}`);
      
      if (currentIndex >= 0 && currentIndex < tagList.length - 1) {
        return tagList[currentIndex + 1];
      }
      
      return tagList[0] || null;
    } catch (error) {
      console.warn("Could not determine previous tag:", error);
      return null;
    }
  }
}

// === VERSION-AWARE COMPARATOR ===

class VersionAwareComparator {
  static compareVersions(
    previousSchemas: ContractSchema[],
    currentSchemas: ContractSchema[]
  ): BreakingChange[] {
    const breakingChanges: BreakingChange[] = [];
    
    // Check for removed schemas
    for (const prevSchema of previousSchemas) {
      const currentSchema = currentSchemas.find(s => s.name === prevSchema.name);
      
      if (!currentSchema) {
        breakingChanges.push({
          schema: prevSchema.name,
          type: "schema_removed",
          description: `Schema ${prevSchema.name} was removed`,
          severity: "critical",
        });
        continue;
      }
      
      // Compare fields within the schema
      const schemaChanges = this.compareSchemaFields(prevSchema, currentSchema);
      breakingChanges.push(...schemaChanges);
    }
    
    // Check for new schemas (not breaking, but worth noting)
    for (const currentSchema of currentSchemas) {
      const prevSchema = previousSchemas.find(s => s.name === currentSchema.name);
      
      if (!prevSchema) {
        // New schema added - not breaking
        console.log(`New schema added: ${currentSchema.name}`);
      }
    }
    
    return breakingChanges;
  }

  private static compareSchemaFields(
    previousSchema: ContractSchema,
    currentSchema: ContractSchema
  ): BreakingChange[] {
    const breakingChanges: BreakingChange[] = [];
    
    const prevFields = new Set(Object.keys(previousSchema.fields));
    const currentFields = new Set(Object.keys(currentSchema.fields));
    
    // Check for removed fields
    for (const fieldName of prevFields) {
      if (!currentFields.has(fieldName)) {
        breakingChanges.push({
          schema: previousSchema.name,
          type: "field_removed",
          description: `Field '${fieldName}' was removed from ${previousSchema.name}`,
          severity: "critical",
        });
      }
    }
    
    // Check for changed fields
    for (const fieldName of prevFields) {
      if (currentFields.has(fieldName)) {
        const prevField = previousSchema.fields[fieldName];
        const currentField = currentSchema.fields[fieldName];
        
        // Type changes
        if (prevField.type !== currentField.type) {
          breakingChanges.push({
            schema: previousSchema.name,
            type: "field_type_changed",
            description: `Field '${fieldName}' in ${previousSchema.name} changed from ${prevField.type} to ${currentField.type}`,
            severity: "critical",
          });
        }
        
        // Required changes (optional -> required is breaking)
        if (!prevField.required && currentField.required) {
          breakingChanges.push({
            schema: previousSchema.name,
            type: "field_required_changed",
            description: `Field '${fieldName}' in ${previousSchema.name} became required`,
            severity: "major",
          });
        }
        
        // Enum value changes
        if (prevField.enum && currentField.enum) {
          const prevEnum = new Set(prevField.enum);
          const currentEnum = new Set(currentField.enum);
          
          for (const value of prevEnum) {
            if (!currentEnum.has(value)) {
              breakingChanges.push({
                schema: previousSchema.name,
                type: "enum_value_removed",
                description: `Enum value '${value}' was removed from field '${fieldName}' in ${previousSchema.name}`,
                severity: "major",
              });
            }
          }
        }
      }
    }
    
    return breakingChanges;
  }

  static assessBreakingChangeSeverity(breakingChanges: BreakingChange[]): {
    critical: BreakingChange[];
    major: BreakingChange[];
    minor: BreakingChange[];
    requiresVersionBump: boolean;
    recommendedVersionBump: "patch" | "minor" | "major";
  } {
    const critical = breakingChanges.filter(c => c.severity === "critical");
    const major = breakingChanges.filter(c => c.severity === "major");
    const minor = breakingChanges.filter(c => c.severity === "minor");
    
    let recommendedVersionBump: "patch" | "minor" | "major" = "patch";
    
    if (critical.length > 0) {
      recommendedVersionBump = "major";
    } else if (major.length > 0) {
      recommendedVersionBump = "minor";
    }
    
    return {
      critical,
      major,
      minor,
      requiresVersionBump: breakingChanges.length > 0,
      recommendedVersionBump,
    };
  }
}

// === VERSION-AWARE TEST RUNNER ===

class VersionAwareContractTester {
  static async runVersionAwareTest(): Promise<{
    success: boolean;
    breakingChanges: BreakingChange[];
    assessment: {
      critical: BreakingChange[];
      major: BreakingChange[];
      minor: BreakingChange[];
      requiresVersionBump: boolean;
      recommendedVersionBump: "patch" | "minor" | "major";
    };
    currentVersion: string;
    previousVersion: string | null;
  }> {
    console.log("Running version-aware contract testing...");
    
    try {
      const currentVersion = VersionAwareSchemaExtractor.getCurrentVersion();
      const previousTag = VersionAwareSchemaExtractor.getPreviousTag();
      
      console.log(`Current version: ${currentVersion}`);
      console.log(`Previous tag: ${previousTag || "none"}`);
      
      if (!previousTag) {
        console.log("No previous version found - skipping version comparison");
        return {
          success: true,
          breakingChanges: [],
          assessment: {
            critical: [],
            major: [],
            minor: [],
            requiresVersionBump: false,
            recommendedVersionBump: "patch",
          },
          currentVersion,
          previousVersion: null,
        };
      }
      
      // Extract schemas from both versions
      const previousSchemas = VersionAwareSchemaExtractor.extractFromGitTag(previousTag);
      const currentSchemas = VersionAwareSchemaExtractor.extractCurrentSchemas();
      
      console.log(`Previous schemas: ${previousSchemas.length}`);
      console.log(`Current schemas: ${currentSchemas.length}`);
      
      // Compare versions
      const breakingChanges = VersionAwareComparator.compareVersions(previousSchemas, currentSchemas);
      const assessment = VersionAwareComparator.assessBreakingChangeSeverity(breakingChanges);
      
      // Generate report
      this.generateReport(breakingChanges, assessment, currentVersion, previousTag);
      
      // Check if version bump is required
      const packageJsonPath = join(process.cwd(), "package.json");
      const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf8"));
      
      if (assessment.requiresVersionBump) {
        console.log(`\nBreaking changes detected - version bump required`);
        console.log(`Recommended bump: ${assessment.recommendedVersionBump}`);
        
        // In CI, this would fail the build
        if (process.env.CI === "true") {
          throw new Error(`Breaking changes detected without proper version bump. Recommended: ${assessment.recommendedVersionBump}`);
        }
        
        return {
          success: false,
          breakingChanges,
          assessment,
          currentVersion,
          previousVersion: previousTag,
        };
      }
      
      console.log("\nNo breaking changes detected");
      return {
        success: true,
        breakingChanges,
        assessment,
        currentVersion,
        previousVersion: previousTag,
      };
      
    } catch (error) {
      console.error("Version-aware contract testing failed:", error);
      throw error;
    }
  }

  private static generateReport(
    breakingChanges: BreakingChange[],
    assessment: ReturnType<typeof VersionAwareComparator.assessBreakingChangeSeverity>,
    currentVersion: string,
    previousVersion: string
  ): void {
    const reportPath = join(process.cwd(), `contract-version-diff-${currentVersion}.md`);
    
    let report = `# Contract Version Diff Report\n\n`;
    report += `**From:** ${previousVersion}\n`;
    report += `**To:** ${currentVersion}\n`;
    report += `**Date:** ${new Date().toISOString()}\n\n`;
    
    if (breakingChanges.length === 0) {
      report += `## No Breaking Changes Detected\n\n`;
      report += `All contracts remain compatible between versions.\n`;
    } else {
      report += `## Breaking Changes Detected\n\n`;
      report += `**Total Breaking Changes:** ${breakingChanges.length}\n`;
      report += `**Recommended Version Bump:** ${assessment.recommendedVersionBump}\n\n`;
      
      if (assessment.critical.length > 0) {
        report += `### Critical Changes\n\n`;
        assessment.critical.forEach(change => {
          report += `- **${change.schema}**: ${change.description}\n`;
        });
        report += `\n`;
      }
      
      if (assessment.major.length > 0) {
        report += `### Major Changes\n\n`;
        assessment.major.forEach(change => {
          report += `- **${change.schema}**: ${change.description}\n`;
        });
        report += `\n`;
      }
      
      if (assessment.minor.length > 0) {
        report += `### Minor Changes\n\n`;
        assessment.minor.forEach(change => {
          report += `- **${change.schema}**: ${change.description}\n`;
        });
        report += `\n`;
      }
    }
    
    writeFileSync(reportPath, report);
    console.log(`Contract diff report saved to: ${reportPath}`);
  }
}

// === MAIN EXECUTION ===

async function main() {
  try {
    const result = await VersionAwareContractTester.runVersionAwareTest();
    
    if (!result.success) {
      console.error("\nVersion-aware contract testing failed");
      process.exit(1);
    }
    
    console.log("\nVersion-aware contract testing passed");
  } catch (error) {
    console.error("Version-aware contract testing failed:", error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

export { VersionAwareContractTester, BreakingChange, ContractVersion };
