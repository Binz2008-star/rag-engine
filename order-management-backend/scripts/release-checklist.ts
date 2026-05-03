// === RELEASE CHECKLIST AUTOMATION ===
// Ensures all release requirements are met before deployment

import { execSync } from "child_process";
import { readFileSync, writeFileSync } from "fs";
import { join } from "path";

// === CHECKLIST ITEMS ===

interface ChecklistItem {
  id: string;
  description: string;
  required: boolean;
  check: () => Promise<boolean>;
  errorMessage: string;
}

// === RELEASE VALIDATOR ===

class ReleaseValidator {
  private checklist: ChecklistItem[] = [];
  private version: string = "";
  private isBreaking: boolean = false;

  constructor(version: string, isBreaking: boolean = false) {
    this.version = version;
    this.isBreaking = isBreaking;
    this.setupChecklist();
  }

  private setupChecklist(): void {
    this.checklist = [
      {
        id: "tests-pass",
        description: "All tests pass (unit, integration, contract)",
        required: true,
        check: async () => this.runTests(),
        errorMessage: "Tests failed - fix issues before release",
      },
      {
        id: "docs-updated",
        description: "Documentation is updated",
        required: true,
        check: async () => this.checkDocumentation(),
        errorMessage: "Documentation not updated - update docs before release",
      },
      {
        id: "changelog-updated",
        description: "Changelog is updated",
        required: true,
        check: async () => this.checkChangelog(),
        errorMessage: "Changelog not updated - add release notes",
      },
      {
        id: "version-bumped",
        description: "Version numbers are bumped",
        required: true,
        check: async () => this.checkVersionBump(),
        errorMessage: "Version not properly bumped - update package.json",
      },
      {
        id: "openapi-regenerated",
        description: "OpenAPI spec is regenerated",
        required: true,
        check: async () => this.checkOpenAPI(),
        errorMessage: "OpenAPI spec not regenerated - run API generation",
      },
      {
        id: "sdk-regenerated",
        description: "SDK is regenerated",
        required: true,
        check: async () => this.checkSDK(),
        errorMessage: "SDK not regenerated - run SDK generation",
      },
      {
        id: "breaking-documented",
        description: "Breaking changes are documented",
        required: this.isBreaking,
        check: async () => this.checkBreakingChanges(),
        errorMessage: "Breaking changes not documented - add migration guide",
      },
      {
        id: "migration-guide",
        description: "Migration guide provided",
        required: this.isBreaking,
        check: async () => this.checkMigrationGuide(),
        errorMessage: "Migration guide missing - create migration documentation",
      },
      {
        id: "security-review",
        description: "Security review completed",
        required: this.isBreaking,
        check: async () => this.checkSecurityReview(),
        errorMessage: "Security review not completed - conduct security assessment",
      },
      {
        id: "performance-baseline",
        description: "Performance baseline established",
        required: false,
        check: async () => this.checkPerformanceBaseline(),
        errorMessage: "Performance baseline not established - run performance tests",
      },
    ];
  }

  // === CHECK IMPLEMENTATIONS ===

  private async runTests(): Promise<boolean> {
    try {
      console.log("Running unit tests...");
      execSync("npm test", { stdio: "pipe" });
      
      console.log("Running integration tests...");
      execSync("npm run test:integration", { stdio: "pipe" });
      
      console.log("Running contract tests...");
      execSync("npm run test:contract", { stdio: "pipe" });
      
      return true;
    } catch (error) {
      console.error("Test failure:", error);
      return false;
    }
  }

  private async checkDocumentation(): Promise<boolean> {
    try {
      // Check if API docs exist and are recent
      const docsPath = join(process.cwd(), "docs/API_CONTRACTS.md");
      const docs = readFileSync(docsPath, "utf8");
      
      // Check if docs mention current version
      if (!docs.includes(this.version)) {
        console.warn("Documentation doesn't mention current version");
        return false;
      }
      
      return true;
    } catch (error) {
      console.error("Documentation check failed:", error);
      return false;
    }
  }

  private async checkChangelog(): Promise<boolean> {
    try {
      const changelogPath = join(process.cwd(), "CHANGELOG.md");
      const changelog = readFileSync(changelogPath, "utf8");
      
      // Check if current version is in changelog
      if (!changelog.includes(`# ${this.version}`)) {
        console.warn("Changelog doesn't include current version");
        return false;
      }
      
      // Check if changelog has recent date
      const today = new Date().toISOString().split("T")[0];
      if (!changelog.includes(today)) {
        console.warn("Changelog doesn't have today's date");
        return false;
      }
      
      return true;
    } catch (error) {
      console.error("Changelog check failed:", error);
      return false;
    }
  }

  private async checkVersionBump(): Promise<boolean> {
    try {
      const packageJsonPath = join(process.cwd(), "package.json");
      const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf8"));
      
      return packageJson.version === this.version;
    } catch (error) {
      console.error("Version check failed:", error);
      return false;
    }
  }

  private async checkOpenAPI(): Promise<boolean> {
    try {
      // Check if OpenAPI spec exists
      const openApiPath = join(process.cwd(), "src/app/api/openapi/route.ts");
      readFileSync(openApiPath, "utf8");
      
      // Try to access OpenAPI endpoint
      const response = execSync("curl -s http://localhost:3000/api/openapi", { 
        encoding: "utf8",
        stdio: "pipe"
      });
      
      const openApiSpec = JSON.parse(response);
      
      // Check if spec includes version
      return openApiSpec.info.version === this.version.split(".")[0] + ".0.0";
    } catch (error) {
      console.error("OpenAPI check failed:", error);
      return false;
    }
  }

  private async checkSDK(): Promise<boolean> {
    try {
      // Check if generated SDK exists
      const sdkPath = join(process.cwd(), "src/generated/runtime-sdk.ts");
      readFileSync(sdkPath, "utf8");
      
      // Check if types exist
      const typesPath = join(process.cwd(), "src/generated/runtime-api.ts");
      readFileSync(typesPath, "utf8");
      
      return true;
    } catch (error) {
      console.error("SDK check failed:", error);
      return false;
    }
  }

  private async checkBreakingChanges(): Promise<boolean> {
    if (!this.isBreaking) return true;
    
    try {
      const breakingChangesPath = join(process.cwd(), "docs/BREAKING_CHANGES.md");
      const breakingChanges = readFileSync(breakingChangesPath, "utf8");
      
      return breakingChanges.includes(this.version);
    } catch (error) {
      console.error("Breaking changes check failed:", error);
      return false;
    }
  }

  private async checkMigrationGuide(): Promise<boolean> {
    if (!this.isBreaking) return true;
    
    try {
      const migrationPath = join(process.cwd(), "docs/MIGRATION_GUIDE.md");
      const migration = readFileSync(migrationPath, "utf8");
      
      return migration.includes(this.version);
    } catch (error) {
      console.error("Migration guide check failed:", error);
      return false;
    }
  }

  private async checkSecurityReview(): Promise<boolean> {
    if (!this.isBreaking) return true;
    
    try {
      const securityPath = join(process.cwd(), "docs/SECURITY_REVIEW.md");
      const security = readFileSync(securityPath, "utf8");
      
      return security.includes(this.version);
    } catch (error) {
      console.error("Security review check failed:", error);
      return false;
    }
  }

  private async checkPerformanceBaseline(): Promise<boolean> {
    try {
      // Check if performance tests have been run recently
      const perfPath = join(process.cwd(), "test-results/performance.json");
      
      try {
        const perfResults = JSON.parse(readFileSync(perfPath, "utf8"));
        const lastRun = new Date(perfResults.timestamp);
        const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
        
        return lastRun > weekAgo;
      } catch {
        // Performance file doesn't exist or is invalid
        console.warn("No performance baseline found");
        return false;
      }
    } catch (error) {
      console.error("Performance baseline check failed:", error);
      return false;
    }
  }

  // === VALIDATION EXECUTION ===

  async validate(): Promise<{
    success: boolean;
    results: Array<{
      id: string;
      description: string;
      passed: boolean;
      required: boolean;
      error?: string;
    }>;
  }> {
    console.log(`\n=== Release Validation for ${this.version} ===`);
    console.log(`Breaking change: ${this.isBreaking ? "YES" : "NO"}\n`);

    const results = [];

    for (const item of this.checklist) {
      console.log(`Checking: ${item.description}...`);
      
      try {
        const passed = await item.check();
        results.push({
          id: item.id,
          description: item.description,
          passed,
          required: item.required,
          error: passed ? undefined : item.errorMessage,
        });
        
        console.log(`${passed ? "PASS" : "FAIL"}: ${item.description}`);
        
        if (!passed && item.required) {
          console.error(`  ERROR: ${item.errorMessage}`);
        }
      } catch (error) {
        console.error(`ERROR checking ${item.id}:`, error);
        results.push({
          id: item.id,
          description: item.description,
          passed: false,
          required: item.required,
          error: `Check failed: ${error}`,
        });
      }
    }

    const success = results.filter(r => r.required).every(r => r.passed);
    
    console.log(`\n=== Validation ${success ? "PASSED" : "FAILED"} ===`);
    
    if (!success) {
      console.log("\nRequired items that failed:");
      results
        .filter(r => !r.passed && r.required)
        .forEach(r => {
          console.log(`  - ${r.description}: ${r.error}`);
        });
    }

    return { success, results };
  }

  // === REPORT GENERATION ===

  generateReport(results: typeof this.checklist): void {
    const report = {
      version: this.version,
      isBreaking: this.isBreaking,
      timestamp: new Date().toISOString(),
      results: results,
      summary: {
        total: results.length,
        passed: results.filter(r => r.passed).length,
        failed: results.filter(r => !r.passed).length,
        required: results.filter(r => r.required).length,
        requiredPassed: results.filter(r => r.required && r.passed).length,
      },
    };

    const reportPath = join(process.cwd(), `release-report-${this.version}.json`);
    writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    console.log(`\nReport saved to: ${reportPath}`);
  }
}

// === MAIN EXECUTION ===

async function main() {
  const args = process.argv.slice(2);
  const version = args[0];
  const isBreaking = args.includes("--breaking");

  if (!version) {
    console.error("Usage: npm run release-checklist <version> [--breaking]");
    process.exit(1);
  }

  const validator = new ReleaseValidator(version, isBreaking);
  const { success, results } = await validator.validate();
  
  validator.generateReport(results);

  if (!success) {
    console.error("\nRelease validation failed. Fix issues before deployment.");
    process.exit(1);
  }

  console.log("\nRelease validation passed. Ready for deployment!");
}

// Run if called directly
if (require.main === module) {
  main().catch((error) => {
    console.error("Release validation failed:", error);
    process.exit(1);
  });
}

export { ReleaseValidator };
