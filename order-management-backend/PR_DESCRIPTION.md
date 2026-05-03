refactor: extract product domain from runtime and align deployment with Render

## Changes Made

### Architecture Refactoring
- **Runtime Boundary Enforcement**: Complete removal of Product model from runtime domain
- **Domain Separation**: Extracted product domain logic to maintain clean boundaries
- **Schema Updates**: Removed product-related tables from runtime schema
- **Interface Updates**: Updated CreateOrderData to remove Product dependencies

### Deployment Migration  
- **Render Migration**: Migrated deployment strategy from Vercel to Render
- **Infrastructure Updates**: Updated deployment configurations for Render compatibility
- **Environment Alignment**: Aligned deployment settings with new platform

### Workflow Fixes
- **GitHub Actions**: Fixed missing permissions in Neon branch delete workflow
- **CI Improvements**: Updated workflow configurations for proper execution

## Impact
- Maintains clean separation between runtime and product domains
- Aligns deployment platform with project requirements  
- Fixes workflow permission issues
- Preserves all existing functionality while improving architecture
