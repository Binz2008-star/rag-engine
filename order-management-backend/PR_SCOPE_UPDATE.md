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

### Code Quality Improvements
- **TypeScript Fixes**: Resolved linting errors and null safety issues
- **Markdown Formatting**: Fixed documentation formatting across all files
- **Workflow Updates**: Fixed GitHub Actions context access patterns

### Impact
- Maintains clean separation between runtime and product domains
- Aligns deployment platform with project requirements  
- Fixes workflow permission issues
- Preserves all existing functionality while improving architecture

## Boundary Compliance
- Product model correctly removed from runtime schema
- Order and Payment models preserved in runtime domain
- All command/query API separation rules followed
- Proper transaction and audit logging maintained
