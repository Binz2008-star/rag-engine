# Rate Limiting Window Model

## Current Implementation: Fixed Window

We use a **fixed window** approach with the following characteristics:

### Window Definition

- **Type**: Fixed (not sliding)
- **Duration**: Configurable via `windowMs` (typically 60 seconds)
- **Reset**: At window expiry (TTL expiration)

### Behavior

```text
Time: 00:00 - 01:00  | 01:00 - 02:00  | 02:00 - 03:00
Window 1 (10 req)    | Window 2 (10 req) | Window 3 (10 req)
```

### Advantages

- **Simple**: Easy to understand and implement
- **Predictable**: Consistent behavior across instances
- **Low overhead**: No sliding window calculations

### Limitations

- **Burst allowance**: Can allow 2x limit at window boundaries
- **Not burst-friendly**: Sharp cut-offs

### Atomicity Guarantee

- **Upstash**: Pipeline `INCR` + `EXPIRE` (atomic)
- **Memory**: Single-threaded increment (atomic)

### Cross-Instance Consistency

- **Redis**: Shared state across all instances
- **Memory fallback**: Per-instance (not cross-instance consistent)

## Future Considerations

### Sliding Window (Potential Upgrade)

```typescript
// More complex but smoother rate limiting
// Requires tracking request timestamps
// Higher memory overhead
```

### Token Bucket (Alternative)

```typescript
// More burst-friendly
// Complex implementation
// Better for API rate limiting
```

## Production Notes

1. **Fixed window is acceptable** for most use cases
2. **Redis ensures cross-instance consistency**
3. **Memory fallback is per-instance** (documented limitation)
4. **Monitor for boundary burst effects**
