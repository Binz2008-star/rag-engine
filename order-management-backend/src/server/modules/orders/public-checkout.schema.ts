import { z } from "zod";

export const createPublicCheckoutSchema = z.object({
  sellerSlug: z.string().min(1),
  customer: z.object({
    name: z.string().min(1).max(120),
    phone: z.string().min(5).max(30),
    addressText: z.string().min(1).max(500),
  }),
  items: z
    .array(
      z.object({
        productId: z.string().min(1),
        quantity: z.number().int().positive(),
      })
    )
    .min(1),
  notes: z.string().max(1000).optional(),
});

export type CreatePublicCheckoutInput = z.infer<typeof createPublicCheckoutSchema>;
