// === OPENAPI-ZOD SYNC VALIDATOR ===
// Ensures OpenAPI spec matches Zod schemas exactly

import { execSync } from "child_process";
import { readFileSync, writeFileSync } from "fs";
import { join } from "path";

// === SCHEMA EXTRACTOR ===

class SchemaExtractor {
  static extractZodSchemas(): Record<string, any> {
    const schemas: Record<string, any> = {};
    
    // Import and extract all Zod schemas
    const {
      CreateOrderSchema,
      UpdateOrderSchema,
      GetOrdersQuery,
      OrderResponseSchema,
      OrderListResponseSchema,
      OrderCreateResponseSchema,
      OrderUpdateResponseSchema,
      ErrorSchema,
    } = require("../src/shared/schemas/orders");
    
    schemas.CreateOrderSchema = CreateOrderSchema;
    schemas.UpdateOrderSchema = UpdateOrderSchema;
    schemas.GetOrdersQuery = GetOrdersQuery;
    schemas.OrderResponseSchema = OrderResponseSchema;
    schemas.OrderListResponseSchema = OrderListResponseSchema;
    schemas.OrderCreateResponseSchema = OrderCreateResponseSchema;
    schemas.OrderUpdateResponseSchema = OrderUpdateResponseSchema;
    schemas.ErrorSchema = ErrorSchema;
    
    return schemas;
  }

  static extractOpenAPISchemas(): Record<string, any> {
    try {
      const openApiPath = join(process.cwd(), "src/shared/openapi/generator.ts");
      const generatorContent = readFileSync(openApiPath, "utf8");
      
      // Extract the OpenApiDocument export
      const documentMatch = generatorContent.match(/export const OpenApiDocument = ({[\s\S]*?});/);
      if (!documentMatch) {
        throw new Error("Could not find OpenApiDocument in generator file");
      }
      
      // Evaluate the document (simplified - in production you'd parse more safely)
      const documentCode = documentMatch[1];
      return eval(`(${documentCode})`);
    } catch (error) {
      throw new Error(`Failed to extract OpenAPI schemas: ${error}`);
    }
  }

  static zodToOpenAPI(zodSchema: any): any {
    // Simplified conversion - in production you'd use zod-to-openapi
    const shape = zodSchema._def?.shape || {};
    const properties: Record<string, any> = {};
    
    for (const [key, value] of Object.entries(shape)) {
      const zodType = (value as any)._def;
      
      if (zodType) {
        properties[key] = this.zodTypeToOpenAPIType(zodType);
      }
    }
    
    return {
      type: "object",
      properties,
      required: Object.keys(properties).filter(key => {
        const field = shape[key];
        return !(field as any)._def?.isOptional;
      }),
    };
  }

  static zodTypeToOpenAPIType(zodDef: any): any {
    if (zodDef.typeName === "ZodString") {
      return { type: "string" };
    }
    
    if (zodDef.typeName === "ZodNumber") {
      return { type: "number" };
    }
    
    if (zodDef.typeName === "ZodBoolean") {
      return { type: "boolean" };
    }
    
    if (zodDef.typeName === "ZodEnum") {
      return { 
        type: "string",
        enum: zodDef.values
      };
    }
    
    if (zodDef.typeName === "ZodArray") {
      return {
        type: "array",
        items: this.zodTypeToOpenAPIType(zodDef.type)
      };
    }
    
    if (zodDef.typeName === "ZodOptional") {
      return this.zodTypeToOpenAPIType(zodDef.innerType);
    }
    
    return { type: "object" }; // fallback
  }
}

// === COMPARISON ENGINE ===

class SchemaComparator {
  static compareSchemas(zodSchemas: Record<string, any>, openApiSchemas: Record<string, any>): {
    isValid: boolean;
    errors: string[];
  } {
    const errors: string[] = [];
    
    // Compare each schema
    for (const [schemaName, zodSchema] of Object.entries(zodSchemas)) {
      const openApiSchema = openApiSchemas.components?.schemas?.[schemaName];
      
      if (!openApiSchema) {
        errors.push(`Missing OpenAPI schema: ${schemaName}`);
        continue;
      }
      
      const zodOpenAPI = SchemaExtractor.zodToOpenAPI(zodSchema);
      const schemaErrors = this.compareSchemaObjects(zodOpenAPI, openApiSchema, schemaName);
      errors.push(...schemaErrors);
    }
    
    // Check for extra OpenAPI schemas
    const openApiSchemaNames = Object.keys(openApiSchemas.components?.schemas || {});
    const zodSchemaNames = Object.keys(zodSchemas);
    
    for (const schemaName of openApiSchemaNames) {
      if (!zodSchemaNames.includes(schemaName)) {
        errors.push(`Extra OpenAPI schema not in Zod: ${schemaName}`);
      }
    }
    
    return {
      isValid: errors.length === 0,
      errors,
    };
  }

  static compareSchemaObjects(zodSchema: any, openApiSchema: any, path: string): string[] {
    const errors: string[] = [];
    
    // Compare type
    if (zodSchema.type !== openApiSchema.type) {
      errors.push(`${path}: Type mismatch (Zod: ${zodSchema.type}, OpenAPI: ${openApiSchema.type})`);
    }
    
    // Compare properties
    if (zodSchema.properties && openApiSchema.properties) {
      const zodProps = Object.keys(zodSchema.properties);
      const openApiProps = Object.keys(openApiSchema.properties);
      
      // Check for missing properties
      for (const prop of zodProps) {
        if (!openApiProps.includes(prop)) {
          errors.push(`${path}: Missing property in OpenAPI: ${prop}`);
        }
      }
      
      // Check for extra properties
      for (const prop of openApiProps) {
        if (!zodProps.includes(prop)) {
          errors.push(`${path}: Extra property in OpenAPI: ${prop}`);
        }
      }
      
      // Compare property types
      for (const prop of zodProps) {
        if (openApiProps.includes(prop)) {
          const zodProp = zodSchema.properties[prop];
          const openApiProp = openApiSchema.properties[prop];
          
          if (zodProp.type !== openApiProp.type) {
            errors.push(`${path}.${prop}: Property type mismatch (Zod: ${zodProp.type}, OpenAPI: ${openApiProp.type})`);
          }
        }
      }
    }
    
    // Compare required fields
    if (zodSchema.required && openApiSchema.required) {
      const zodRequired = new Set(zodSchema.required);
      const openApiRequired = new Set(openApiSchema.required);
      
      for (const field of zodRequired) {
        if (!openApiRequired.has(field)) {
          errors.push(`${path}: Required field missing in OpenAPI: ${field}`);
        }
      }
      
      for (const field of openApiRequired) {
        if (!zodRequired.has(field)) {
          errors.push(`${path}: Extra required field in OpenAPI: ${field}`);
        }
      }
    }
    
    return errors;
  }
}

// === SYNC VALIDATOR ===

class OpenAPISyncValidator {
  static async validate(): Promise<void> {
    console.log("Validating OpenAPI-Zod sync...");
    
    try {
      // Extract schemas
      const zodSchemas = SchemaExtractor.extractZodSchemas();
      const openApiSchemas = SchemaExtractor.extractOpenAPISchemas();
      
      // Compare schemas
      const comparison = SchemaComparator.compareSchemas(zodSchemas, openApiSchemas);
      
      if (!comparison.isValid) {
        console.error("OpenAPI-Zod sync validation failed:");
        comparison.errors.forEach(error => console.error(`  - ${error}`));
        
        console.error("\nTo fix this:");
        console.error("1. Run: npm run generate-openapi");
        console.error("2. Commit the generated changes");
        
        process.exit(1);
      }
      
      console.log("PASS: OpenAPI spec is in sync with Zod schemas");
      
    } catch (error) {
      console.error("Sync validation failed:", error);
      process.exit(1);
    }
  }

  static async generateOpenAPI(): Promise<void> {
    console.log("Generating OpenAPI spec from Zod schemas...");
    
    try {
      // Extract schemas
      const zodSchemas = SchemaExtractor.extractZodSchemas();
      
      // Generate OpenAPI document
      const openApiDocument = {
        openapi: "3.0.0",
        info: {
          title: "Order Management API",
          version: "1.0.0",
          description: "Production-grade order management system with contract enforcement",
        },
        components: {
          schemas: Object.fromEntries(
            Object.entries(zodSchemas).map(([name, schema]) => [
              name,
              SchemaExtractor.zodToOpenAPI(schema)
            ])
          ),
        },
      };
      
      // Write to generator file
      const generatorPath = join(process.cwd(), "src/shared/openapi/generator.ts");
      const generatorContent = `// === AUTO-GENERATED OPENAPI DOCUMENT ===
// Generated from Zod schemas - DO NOT EDIT MANUALLY

export const OpenApiDocument = ${JSON.stringify(openApiDocument, null, 2)};
`;
      
      writeFileSync(generatorPath, generatorContent);
      console.log("OpenAPI spec generated successfully");
      
    } catch (error) {
      console.error("Failed to generate OpenAPI spec:", error);
      process.exit(1);
    }
  }
}

// === MAIN EXECUTION ===

async function main() {
  const command = process.argv[2];
  
  switch (command) {
    case "validate":
      await OpenAPISyncValidator.validate();
      break;
      
    case "generate":
      await OpenAPISyncValidator.generateOpenAPI();
      break;
      
    default:
      console.error("Usage: npm run validate-openapi [validate|generate]");
      process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch((error) => {
    console.error("OpenAPI sync validation failed:", error);
    process.exit(1);
  });
}

export { OpenAPISyncValidator };
