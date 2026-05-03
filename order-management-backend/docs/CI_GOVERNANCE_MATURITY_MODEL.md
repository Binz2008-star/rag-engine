# CI Governance Maturity Model

**Version:** 1.0.0  
**Status:** Active Planning Document  
**Purpose:** Define clear path from heuristic governance to authoritative system-wide enforcement

---

## Executive Summary

Current state: **Declared governance with partial heuristic enforcement, below merge-authoritative maturity**

**Target:** 3-layer maturity progression from policy declaration to cross-repo authoritative governance

---

## Maturity Layers

### L1 - Policy Declaration + Basic Guardrails

**Objective:** Establish governance rules and prevent naive violations  
**Current Status:** Partially implemented

#### What Exists
- `docs/domain-ownership.yml` - governance declaration
- `.github/workflows/architecture-enforcement.yml` - enforcement attempt
- Basic textual guardrails

#### What's Missing for L1 Completion
- [ ] **OS Compatibility Fix** - `findstr`/Windows paths on `ubuntu-latest` runner
- [ ] **Evidence Artifacts** - Convert source snapshots to JSON evidence reports
- [ ] **Workflow Execution Validation** - Confirm workflow runs without OS errors

#### L1 Definition of Done
- [ ] Policy file exists and is parseable
- [ ] Workflow executes correctly on target runner
- [ ] Basic checks don't fail due to environment mismatch
- [ ] Artifacts clearly explain what failed and why

---

### L2 - Repo-Consistent Blocking Enforcement

**Objective:** Merge-relevant governance with repo-specific, reality-derived rules  
**Current Status:** Not implemented

#### Required Capabilities
- **Schema-derived rules** - Rules derived from actual `prisma/schema.prisma`
- **Repo-aware path maps** - Specific allowed/forbidden paths per repo
- **Blocking behavior** - Required checks before merge
- **Executable evidence** - JSON logs, SARIF, machine-readable reports

#### Implementation Requirements

##### 1. Schema-Derived Rules
```yaml
# Current issue: Rules reference non-existent models
# Fix: Derive from actual schema
actual_models:
  - User
  - user  # lowercase model in schema
  - PaymentAttempt  # not "Payment"
  - session  # lowercase, not "Session"
  - Seller
```

##### 2. Repo-Aware Path Maps
```yaml
# Replace generic patterns with specific path mappings
order-management-backend:
  forbidden_imports:
    - "from.*../../server"  # API routes importing server internals
    - "prisma\\.(order|payment|user)\\.(create|update)"  # Direct mutations
  
allowed_paths:
  - "src/app/api/*/route.ts"  # API route files
  - "src/server/lib/*"  # Server library modules
```

##### 3. Blocking Enforcement
```yaml
# Required PR checks
required_checks:
  - architecture-enforcement
  - domain-ownership-validation
  - schema-authority-check
```

#### L2 Definition of Done
- [ ] Workflow executes successfully on correct runner
- [ ] Rules derived from current schema
- [ ] False positives significantly reduced
- [ ] False negatives eliminated from rule/reality mismatch
- [ ] Check required before merge in this repo

---

### L3 - Semantically Authoritative Cross-Repo Governance

**Objective:** System-wide authoritative governance across all repos  
**Current Status:** Not implemented

#### Required Capabilities
- **Authoritative shared governance source** - Central or shared ruleset
- **Cross-repo bindings** - Same ownership graph applied across repos
- **Semantic checks** - Model ownership, mutation authority, import authority
- **Transitional state encoding** - Time-limited allowlists for decomposition

#### Implementation Requirements

##### 1. Authoritative Governance Source
Option A: Centralized repo
```
governance-repo/
  docs/domain-ownership.yml
  .github/workflows/enforcement.yml
  packages/governance-rules/
```

Option B: Shared package
```
@governance/rules
  domain-ownership.json
  enforcement-engine.js
```

##### 2. Cross-Repo Application
```yaml
repos:
  - order-management-backend
  - sellora  
  - omb-retrieval
  
shared_governance:
  source: governance-repo
  enforcement: required
  authority: system-wide
```

##### 3. Semantic Check Examples
```javascript
// Not just string matching
if (prismaModelMutation(modelName)) {
  if (!ownsMutation(repo, modelName)) {
    fail(`Mutation authority violation: ${repo} cannot mutate ${modelName}`)
  }
}

// Schema ownership validation
if (modelDefinitionExists(modelName)) {
  if (!ownsSchema(repo, modelName)) {
    fail(`Schema authority violation: ${repo} cannot define ${modelName}`)
  }
}
```

#### L3 Definition of Done
- [ ] Same governance source applied across all repos
- [ ] Authority graph clearly defined and enforced
- [ ] Merge blocked for real boundary violations, not pattern matches
- [ ] Ownership becomes system-wide, not repo-local

---

## Current State Assessment

### Layer Status
- **L1:** Partially implemented (OS issues, evidence gaps)
- **L2:** Not implemented (reality-derivation missing)
- **L3:** Not implemented (cross-repo authority missing)

### Critical Gaps
1. **Execution Gap** - Workflow won't run on target environment
2. **Reality Gap** - Rules don't match actual schema/models
3. **Authority Gap** - No cross-repo enforcement mechanism
4. **Evidence Gap** - No machine-readable compliance reports

### Risk Assessment
- **Current Risk:** Medium (governance declared but not enforceable)
- **Without L2:** High (rules may be ignored or incorrect)
- **Without L3:** Critical (system-wide boundaries unenforced)

---

## Implementation Roadmap

### Phase 1: Complete L1 (Immediate Priority)
**Timeline:** 1-2 days
**Effort:** Low

#### Tasks
1. Fix OS compatibility in workflow
2. Generate JSON evidence artifacts
3. Validate workflow execution
4. Update documentation

#### Success Criteria
- Workflow runs on `ubuntu-latest`
- Evidence artifacts are machine-readable
- Basic checks execute without errors

---

### Phase 2: Implement L2 (Short-term Priority)
**Timeline:** 1-2 weeks
**Effort:** Medium

#### Tasks
1. Schema-derived rule generation
2. Repo-aware path mapping
3. Blocking enforcement configuration
4. Required PR check setup

#### Success Criteria
- Rules match actual schema
- No false positives from generic patterns
- Merge blocked for violations
- Evidence reports include specific violations

---

### Phase 3: Design L3 (Medium-term Priority)
**Timeline:** 2-4 weeks
**Effort:** High

#### Tasks
1. Cross-repo governance architecture
2. Shared governance source design
3. Semantic check implementation
4. Transitional state management

#### Success Criteria
- Governance shared across repos
- Semantic authority validation
- System-wide boundary enforcement

---

## Decision Gates

### L1 Completion Gate
- [ ] Workflow executes without OS errors
- [ ] Evidence artifacts are JSON/machine-readable
- [ ] Basic guardrails prevent obvious violations

### L2 Completion Gate
- [ ] All rules derived from actual schema
- [ ] No false positives from generic patterns
- [ ] Merge blocked for real violations
- [ ] Evidence includes specific violation details

### L3 Completion Gate
- [ ] Same governance applied across repos
- [ ] Authority violations blocked system-wide
- [ ] Semantic checks understand model ownership
- [ ] Transitional allowlists time-limited

---

## Success Metrics

### Quantitative
- **L1:** Workflow success rate > 95%
- **L2:** False positive rate < 5%, false negative rate = 0
- **L3:** Cross-repo consistency = 100%

### Qualitative
- **L1:** Team trusts basic guardrails
- **L2:** Developers understand violation reasons
- **L3:** Architecture changes require explicit authority

---

## Next Steps

1. **Immediate:** Fix L1 OS compatibility issues
2. **Short-term:** Begin L2 schema-derived rules
3. **Parallel:** Document current ownership boundaries
4. **Future:** Plan L3 cross-repo architecture

---

## Appendix

### Current File References
- `docs/domain-ownership.yml` - Governance declaration
- `.github/workflows/architecture-enforcement.yml` - Enforcement attempt
- `prisma/schema.prisma` - Source of truth for models
- `src/` - Target for enforcement rules

### Related Documentation
- Domain Ownership Graph (DOG)
- Architecture Enforcement Workflow
- Schema Authority Documentation
