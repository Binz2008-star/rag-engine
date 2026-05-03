// Note: There is no Product table in the schema.
// Products are referenced by ID only in order items.
// The V1 API now accepts any string ID directly — no external ID translation.

let productCounter = 0

/**
 * Generate a unique product ID for testing.
 * Since there is no Product table, any non-empty string is valid.
 */
export function generateProductId(): string {
  productCounter++
  return `test-product-${Date.now()}-${productCounter}`
}

/**
 * Returns a stable product ID for deterministic tests.
 */
export function getValidTestProductId(): string {
  return 'test-product-001'
}
