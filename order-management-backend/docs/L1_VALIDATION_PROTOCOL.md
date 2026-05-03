# L1 Validation Protocol

**Version:** 1.0.0  
**Status:** Verification Checklist  
**Purpose:** Convert L1 from "configured" to "verified" with evidence-based validation

---

## Executive Summary

**Current State:** L1 prototype / partial CI heuristics  
**Target:** L1 verified with operational evidence and merge-gate enforcement

**Critical Gap:** Configuration exists without verification of actual execution, branch protection, or artifact generation.

---

## Validation Overview

### What L1 Claims vs What Must Be Verified

| Claim | Evidence Required | Current Status |
|-------|-------------------|----------------|
| OS compatibility works | CI run logs showing successful execution on ubuntu-latest | UNVERIFIED |
| Evidence artifacts generated | Actual JSON uploads in CI artifacts | UNVERIFIED |
| Merge gate enforcement | Branch protection rules requiring checks | UNVERIFIED |
| Blocking behavior | Test PR with deliberate violation | UNVERIFIED |

---

## Section 1: Evidence Requirements

### 1.1 CI Execution Evidence
- **Required:** CI workflow run logs from `ubuntu-latest` runner
- **Format:** GitHub Actions workflow execution logs
- **Verification Points:**
  - No OS compatibility errors (findstr/grep issues)
  - All L1 checks execute without environment failures
  - Workflow completes with success/failure status

### 1.2 Artifact Generation Evidence  
- **Required:** Uploaded artifacts from CI run
- **Format:** JSON evidence files in GitHub Actions artifacts
- **Verification Points:**
  - `evidence.json` artifact exists
  - Content matches expected structure
  - Timestamp and run_id populated correctly

### 1.3 Branch Protection Evidence
- **Required:** GitHub branch protection configuration
- **Format:** Branch protection rules screenshot or API response
- **Verification Points:**
  - Required status checks include architecture enforcement
  - Merge blocked on check failure
  - Rules applied to target branches (main/develop)

---

## Section 2: Pass/Fail Criteria

### 2.1 Workflow Execution Criteria
```yaml
PASS:
  - Workflow runs on ubuntu-latest without OS errors
  - All L1 checks execute (no skipped steps)
  - Workflow completes with defined status

FAIL:
  - OS compatibility errors (findstr/grep issues)
  - Steps skipped due to environment mismatch
  - Workflow timeout or undefined failure
```

### 2.2 Evidence Generation Criteria
```yaml
PASS:
  - evidence.json artifact uploaded
  - Artifact contains valid JSON structure
  - Required fields present (timestamp, run_id, checks)

FAIL:
  - No artifacts uploaded
  - Invalid JSON structure
  - Missing required fields
```

### 2.3 Merge Gate Criteria
```yaml
PASS:
  - Branch protection requires architecture enforcement check
  - Merge blocked when check fails
  - Check status visible in PR interface

FAIL:
  - No branch protection rules
  - Check not required for merge
  - Merge allowed despite check failure
```

---

## Section 3: Branch Protection Verification

### 3.1 Required Configuration
```yaml
Branch: main, develop
Required Status Checks:
  - "build-and-test" (existing)
  - "Architecture enforcement checks" (new)
Enforcement:
  - Require branches to be up to date
  - Require status checks to pass before merge
  - Require conversation resolution if enabled
```

### 3.2 Verification Steps
1. Navigate to repository Settings > Branches
2. Check branch protection rules for main/develop
3. Verify required status checks include architecture enforcement
4. Confirm merge restrictions are active

### 3.3 Evidence Collection
- Screenshot of branch protection configuration
- API response from GitHub branch protection endpoint
- Test PR demonstrating merge block

---

## Section 4: Intentional Violation Test

### 4.1 Test Scenarios
```yaml
Test 1 - Cross-domain Import:
  - Add: `import { something } from "../../server"` in API route
  - Expected: CI failure with cross-domain import error
  - Evidence: CI logs showing violation detection

Test 2 - Schema Duplication:
  - Add: `model User` duplicate in src/
  - Expected: CI failure with schema duplication error
  - Evidence: CI logs showing schema authority violation

Test 3 - Auth Logic in API:
  - Add: `bcrypt.hash()` in API route
  - Expected: CI failure with auth authority error
  - Evidence: CI logs showing auth centralization violation
```

### 4.2 Test Execution
1. Create feature branch for violation testing
2. Intentionally add violation code
3. Push branch and create PR
4. Verify CI failure and merge block
5. Clean up branch after verification

### 4.3 Success Criteria
- All violation types detected correctly
- CI fails with appropriate error messages
- Merge blocked until violations fixed
- False positive rate minimal

---

## Section 5: Artifact Verification Matrix

### 5.1 Expected Artifact Structure
```json
{
  "timestamp": "2026-04-10T19:45:00Z",
  "run_id": "1234567890",
  "repo": "order-management-backend",
  "layer": "L1",
  "checks": {
    "cross_domain_imports": "PASS",
    "schema_authority": "PASS", 
    "auth_authority": "PASS",
    "enforcement_level": "L1_COMPLETE"
  }
}
```

### 5.2 Verification Checklist
- [ ] Artifact uploaded to GitHub Actions
- [ ] JSON structure valid and parseable
- [ ] All required fields populated
- [ ] Check statuses accurate
- [ ] Timestamp matches CI execution time
- [ ] Run ID matches CI execution

### 5.3 Failure Modes
```yaml
Missing Artifact:
  - Impact: Cannot verify L1 execution
  - Resolution: Fix artifact upload in workflow

Invalid JSON:
  - Impact: Evidence unreadable
  - Resolution: Fix JSON generation logic

Missing Fields:
  - Impact: Incomplete verification
  - Resolution: Update evidence template
```

---

## Section 6: Validation Timeline

### Phase 1: Evidence Collection (1-2 hours)
- Run CI workflow and collect logs
- Download and verify artifacts
- Document branch protection status

### Phase 2: Violation Testing (2-3 hours)  
- Create intentional violation PRs
- Verify CI failure and merge block
- Document test results

### Phase 3: Documentation (1 hour)
- Complete validation checklist
- Generate validation report
- Update maturity model status

---

## Section 7: Success Definition

### L1 Verified Definition
```yaml
Requirements Met:
  - CI workflow executes successfully on ubuntu-latest
  - Evidence artifacts generated and uploaded
  - Branch protection requires architecture enforcement
  - Violation testing confirms blocking behavior
  - All validation criteria passed

Outcome:
  - L1 status changes from "prototype" to "verified"
  - Foundation established for L2 implementation
  - Governance declared and operational
```

### Failure Modes and Next Steps
```yaml
CI Execution Fails:
  - Fix OS compatibility issues
  - Retry validation after fixes
  - Document resolution steps

Evidence Missing:
  - Fix artifact generation
  - Re-run CI with proper uploads
  - Verify artifact structure

Merge Gate Missing:
  - Configure branch protection
  - Add required status checks
  - Test merge blocking behavior
```

---

## Section 8: Deliverables

### Validation Report
- Evidence collection summary
- Test execution results  
- Pass/fail status for all criteria
- Recommendations for L2 preparation

### Updated Documentation
- CI governance maturity model status
- Architecture enforcement workflow verification
- Branch protection configuration documentation

### Implementation Ready
- L1 verified and ready for L2 planning
- Evidence-based foundation for governance
- Clear path to next maturity layer

---

**Next Step:** Execute validation protocol to convert L1 from prototype to verified status before proceeding to L2 implementation.
