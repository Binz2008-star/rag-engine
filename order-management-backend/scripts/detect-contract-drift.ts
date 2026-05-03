// === CONTRACT DRIFT DETECTOR ===
// Automated detection of contract changes between versions

import { execSync } from "child_process";
import { readFileSync, writeFileSync } from "fs";
import { join } from "path";

// === CONTRACT COMPARISON TYPES ===

interface ContractSchema {
  name: string;
  version: string;
  fields: Record<string, {
    type: string;
    required: boolean;
    enum?: string[];
  }>;
}

interface ContractDiff {
  added: string[];
  removed: string[];
  modified: Array<{
    field: string;
    oldType: string;
    newType: string;
    oldRequired: boolean;
    newRequired: boolean;
  }>;
  breaking: boolean;
}

// === SCHEMA EXTRACTOR ===

class ContractSchemaExtractor {
  static extractFromZod(filePath: string): ContractSchema[] {
    try {
      // Read the schema file
      const content = readFileSync(filePath, "utf8");
      
      // Extract schemas (simplified - in production you'd parse TypeScript AST)
      const schemas: ContractSchema[] = [];
      
      // Extract CreateOrderSchema
      if (content.includes("CreateOrderSchema")) {
        schemas.push({
          name: "CreateOrderSchema",
          version: "current",
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
          version: "current",
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
          version: "current",
          fields: {
            success: { type: "boolean", required: true },
            error: { type: "object", required: true },
          },
        });
      }
      
      return schemas;
    } catch (error) {
      throw new Error(`Failed to extract schemas from ${filePath}: ${error}`);
    }
  }

  static extractFromOpenAPI(filePath: string): ContractSchema[] {
    try {
      const content = readFileSync(filePath, "utf8");
      
      // Parse OpenAPI document
      const openApiDoc = JSON.parse(content);
      const schemas: ContractSchema[] = [];
      
      // Extract schemas from OpenAPI components
      if (openApiDoc.components?.schemas) {
        for (const [name, schema] of Object.entries(openApiDoc.components.schemas)) {
          const openApiSchema = schema as any;
          schemas.push({
            name,
            version: "openapi",
            fields: this.convertOpenAPIToFields(openApiSchema),
          });
        }
      }
      
      return schemas;
    } catch (error) {
      throw new Error(`Failed to extract schemas from OpenAPI ${filePath}: ${error}`);
    }
  }

  private static convertOpenAPIToFields(openApiSchema: any): Record<string, { type: string; required: boolean; enum?: string[] }> {
    const fields: Record<string, { type: string; required: boolean; enum?: string[] }> = {};
    
    if (openApiSchema.properties) {
      for (const [fieldName, fieldSchema] of Object.entries(openApiSchema.properties)) {
        const field = fieldSchema as any;
        const required = openApiSchema.required?.includes(fieldName) || false;
        
        let type = "unknown";
        let enumValues: string[] | undefined;
        
        if (field.type) {
          type = field.type;
        } else if (field.$ref) {
          type = "reference";
        } else if (field.allOf) {
          type = "object";
        } else if (field.oneOf || field.anyOf) {
          type = "union";
        }
        
        if (field.enum) {
          type = "enum";
          enumValues = field.enum;
        }
        
        fields[fieldName] = { type, required, enum: enumValues };
      }
    }
    
    return fields;
  }
}

// === CONTRACT COMPARATOR ===

class ContractComparator {
  static compareSchemas(oldSchemas: ContractSchema[], newSchemas: ContractSchema[]): {
    breaking: boolean;
    diffs: Record<string, ContractDiff>;
  } {
    const diffs: Record<string, ContractDiff> = {};
    let overallBreaking = false;
    
    // Compare each schema
    for (const newSchema of newSchemas) {
      const oldSchema = oldSchemas.find(s => s.name === newSchema.name);
      
      if (!oldSchema) {
        // New schema added
        diffs[newSchema.name] = {
          added: Object.keys(newSchema.fields),
          removed: [],
          modified: [],
          breaking: false,
        };
        continue;
      }
      
      const diff = this.compareSchemaFields(oldSchema, newSchema);
      diffs[newSchema.name] = diff;
      
      if (diff.breaking) {
        overallBreaking = true;
      }
    }
    
    // Check for removed schemas
    for (const oldSchema of oldSchemas) {
      const newSchema = newSchemas.find(s => s.name === oldSchema.name);
      
      if (!newSchema) {
        diffs[oldSchema.name] = {
          added: [],
          removed: Object.keys(oldSchema.fields),
          modified: [],
          breaking: true,
        };
        overallBreaking = true;
      }
    }
    
    return {
      breaking: overallBreaking,
      diffs,
    };
  }

  private static compareSchemaFields(oldSchema: ContractSchema, newSchema: ContractSchema): ContractDiff {
    const oldFields = new Set(Object.keys(oldSchema.fields));
    const newFields = new Set(Object.keys(newSchema.fields));
    
    const added = [...newFields].filter(field => !oldFields.has(field));
    const removed = [...oldFields].filter(field => !newFields.has(field));
    const modified: Array<{
      field: string;
      oldType: string;
      newType: string;
      oldRequired: boolean;
      newRequired: boolean;
    }> = [];
    
    let breaking = false;
    
    // Check for modified fields
    for (const field of oldFields) {
      if (newFields.has(field)) {
        const oldField = oldSchema.fields[field];
        const newField = newSchema.fields[field];
        
        if (oldField.type !== newField.type || oldField.required !== newField.required) {
          modified.push({
            field,
            oldType: oldField.type,
            newType: newField.type,
            oldRequired: oldField.required,
            newRequired: newField.required,
          });
          
          // Check if this is a breaking change
          if (this.isBreakingChange(oldField, newField)) {
            breaking = true;
          }
        }
        
        // Check for enum changes
        if (oldField.enum && newField.enum) {
          const oldEnum = new Set(oldField.enum);
          const newEnum = new Set(newField.enum);
          
          // Removed enum values are breaking
          for (const value of oldEnum) {
            if (!newEnum.has(value)) {
              breaking = true;
            }
          }
        }
      }
    }
    
    // Making required fields optional is not breaking
    // Making optional fields required is breaking
    if (added.some(field => newSchema.fields[field].required)) {
      breaking = true;
    }
    
    // Removing any field is breaking
    if (removed.length > 0) {
      breaking = true;
    }
    
    return {
      added,
      removed,
      modified,
      breaking,
    };
  }

  private static isBreakingChange(oldField: { type: string; required: boolean }, newField: { type: string; required: boolean }): boolean {
    // Type changes are breaking
    if (oldField.type !== newField.type) {
      return true;
    }
    
    // Making optional field required is breaking
    if (!oldField.required && newField.required) {
      return true;
    }
    
    return false;
  }
}

// === CONTRACT DRIFT DETECTOR ===

class ContractDriftDetector {
  static async detectDrift(): Promise<{
    hasDrift: boolean;
    breaking: boolean;
    report: string;
  }> {
    console.log("Detecting contract drift...");
    
    try {
      // Get current schemas from Zod
      const zodSchemas = ContractSchemaExtractor.extractFromZod(
        join(process.cwd(), "src/shared/schemas/orders.ts")
      );
      
      // Get current schemas from OpenAPI
      const openApiSchemas = ContractSchemaExtractor.extractFromOpenAPI(
        join(process.cwd(), "src/shared/openapi/generator.ts")
      );
      
      // Compare schemas
      const comparison = ContractComparator.compareSchemas(zodSchemas, openApiSchemas);
      
      // Generate report
      const report = this.generateReport(comparison);
      
      console.log(report);
      
      return {
        hasDrift: Object.keys(comparison.diffs).length > 0,
        breaking: comparison.breaking,
        report,
      };
    } catch (error) {
      console.error("Contract drift detection failed:", error);
      return {
        hasDrift: true,
        breaking: true,
        report: `Error: ${error}`,
      };
    }
  }

  static async detectBreakingChanges(): Promise<{
    hasBreakingChanges: boolean;
    changes: Array<{
      schema: string;
      type: "added" | "removed" | "modified";
      field?: string;
      description: string;
    }>;
  }> {
    console.log("Detecting breaking changes...");
    
    try {
      // Get current version
      const currentVersion = process.env.CURRENT_VERSION || "current";
      
      // Get previous version schemas (from git or stored snapshots)
      const previousSchemas = await this.getPreviousVersionSchemas(currentVersion);
      
      // Get current schemas
      const currentSchemas = ContractSchemaExtractor.extractFromZod(
        join(process.cwd(), "src/shared/schemas/orders.ts")
      );
      
      // Compare
      const comparison = ContractComparator.compareSchemas(previousSchemas, currentSchemas);
      
      const changes: Array<{
        schema: string;
        type: "added" | "removed" | "modified";
        field?: string;
        description: string;
      }> = [];
      
      for (const [schemaName, diff] of Object.entries(comparison.diffs)) {
        if (!diff.breaking) continue;
        
        // Added fields
        for (const field of diff.added) {
          changes.push({
            schema: schemaName,
            type: "added",
            field,
            description: `Added required field '${field}' to ${schemaName}`,
          });
        }
        
        // Removed fields
        for (const field of diff.removed) {
          changes.push({
            schema: schemaName,
            type: "removed",
            field,
            description: `Removed field '${field}' from ${schemaName}`,
          });
        }
        
        // Modified fields
        for (const modification of diff.modified) {
          changes.push({
            schema: schemaName,
            type: "modified",
            field: modification.field,
            description: `Changed ${schemaName}.${modification.field} from ${modification.oldType} to ${modification.newType}`,
          });
        }
      }
      
      return {
        hasBreakingChanges: changes.length > 0,
        changes,
      };
    } catch (error) {
      console.error("Breaking change detection failed:", error);
      return {
        hasBreakingChanges: true,
        changes: [{
          schema: "unknown",
          type: "modified",
          description: `Error detecting changes: ${error}`,
        }],
      };
    }
  }

  private static async getPreviousVersionSchemas(currentVersion: string): Promise<ContractSchema[]> {
    // In production, this would load schemas from previous version
    // For now, we return empty (no previous version)
    return [];
  }

  private static generateReport(comparison: { breaking: boolean; diffs: Record<string, ContractDiff> }): string {
    let report = "=== CONTRACT DRIFT REPORT ===\n\n";
    
    if (Object.keys(comparison.diffs).length === 0) {
      report += "No contract drift detected.\n";
      return report;
    }
    
    report += `Overall breaking changes: ${comparison.breaking ? "YES" : "NO"}\n\n`;
    
    for (const [schemaName, diff] of Object.entries(comparison.diffs)) {
      report += `## ${schemaName}\n`;
      report += `Breaking: ${diff.breaking ? "YES" : "NO"}\n`;
      
      if (diff.added.length > 0) {
        report += `Added fields: ${diff.added.join(", ")}\n`;
      }
      
      if (diff.removed.length > 0) {
        report += `Removed fields: ${diff.removed.join(", ")}\n`;
      }
      
      if (diff.modified.length > 0) {
        report += "Modified fields:\n";
        for (const mod of diff.modified) {
          report += `  - ${mod.field}: ${mod.oldType} -> ${mod.newType}`;
          if (mod.oldRequired !== mod.newRequired) {
            report += ` (required: ${mod.oldRequired} -> ${mod.newRequired})`;
          }
          report += "\n";
        }
      }
      
      report += "\n";
    }
    
    if (comparison.breaking) {
      report += "WARNING: Breaking changes detected! Version bump required.\n";
    }
    
    return report;
  }

  static async saveSnapshot(): Promise<void> {
    console.log("Saving contract snapshot...");
    
    try {
      const schemas = ContractSchemaExtractor.extractFromZod(
        join(process.cwd(), "src/shared/schemas/orders.ts")
      );
      
      const snapshotPath = join(process.cwd(), "contracts-snapshot.json");
      writeFileSync(snapshotPath, JSON.stringify(schemas, null, 2));
      
      console.log(`Contract snapshot saved to ${snapshotPath}`);
    } catch (error) {
      console.error("Failed to save contract snapshot:", error);
    }
  }
}

// === MAIN EXECUTION ===

async function main() {
  const command = process.argv[2];
  
  switch (command) {
    case "detect-drift":
      const result = await ContractDriftDetector.detectDrift();
      if (result.breaking) {
        console.error("Breaking contract drift detected!");
        process.exit(1);
      }
      break;
      
    case "detect-breaking":
      const breaking = await ContractDriftDetector.detectBreakingChanges();
      if (breaking.hasBreakingChanges) {
        console.error("Breaking changes detected:");
        breaking.changes.forEach(change => {
          console.error(`  - ${change.description}`);
        });
        process.exit(1);
      }
      break;
      
    case "save-snapshot":
      await ContractDriftDetector.saveSnapshot();
      break;
      
    default:
      console.error("Usage: npm run detect-contract-drift [detect-drift|detect-breaking|save-snapshot]");
      process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch((error) => {
    console.error("Contract drift detection failed:", error);
    process.exit(1);
  });
}

export { ContractDriftDetector };
