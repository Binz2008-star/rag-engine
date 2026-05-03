import type { Customer, Order, OrderItem } from "@prisma/client";

export interface PublicCheckoutCustomerInput {
  name: string;
  phone: string;
  addressText: string;
}

export interface PublicCheckoutItemInput {
  productId: string;
  quantity: number;
}

export interface CreatePublicCheckoutCommand {
  sellerSlug: string;
  customer: PublicCheckoutCustomerInput;
  items: PublicCheckoutItemInput[];
  notes?: string;
}

export interface PublicCheckoutPricedItem {
  productId: string;
  productNameSnapshot: string;
  unitPriceMinor: number;
  quantity: number;
  lineTotalMinor: number;
}

export type HydratedPublicCheckoutOrder = Order & {
  customer: Customer;
  orderItems: OrderItem[];
};

export interface PublicCheckoutResponse {
  id: string;
  publicOrderNumber: string;
  status: string;
  paymentStatus: string;
  paymentType: string | null;
  subtotalMinor: number;
  deliveryFeeMinor: number;
  totalMinor: number;
  currency: string;
  notes: string | null;
  source: string;
  createdAt: Date;
  updatedAt: Date;
  customer: {
    id: string;
    name: string;
    phone: string;
    addressText: string;
  };
  items: Array<{
    id: string;
    productId: string;
    productNameSnapshot: string;
    unitPriceMinor: number;
    quantity: number;
    lineTotalMinor: number;
  }>;
}
