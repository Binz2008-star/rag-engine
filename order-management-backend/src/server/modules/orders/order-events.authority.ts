import type { Prisma } from "@prisma/client";

export interface OrderEventAuthorityInput {
  orderId: string;
  eventType: string;
  actorUserId?: string | null;
  payload?: Record<string, unknown> | null;
}

export class OrderEventsAuthority {
  async createOrderEvent(
    tx: Prisma.TransactionClient,
    input: OrderEventAuthorityInput
  ) {
    const { orderId, eventType, actorUserId = null, payload } = input;

    return tx.orderEvent.create({
      data: {
        orderId,
        eventType,
        actorUserId,
        payloadJson: payload ? JSON.stringify(payload) : null,
      },
    });
  }
}

export const orderEventsAuthority = new OrderEventsAuthority();
export const createOrderEvent = orderEventsAuthority.createOrderEvent.bind(orderEventsAuthority);
