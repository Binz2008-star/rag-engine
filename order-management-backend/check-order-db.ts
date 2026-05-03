import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function checkOrderDB() {
  try {
    console.log('🔍 Checking order-related database state...')
    
    const orderCount = await prisma.order.count()
    const orderItemCount = await prisma.orderItem.count()
    const orderEventCount = await prisma.orderEvent.count()
    
    console.log(`Orders: ${orderCount}`)
    console.log(`Order Items: ${orderItemCount}`)
    console.log(`Order Events: ${orderEventCount}`)
    
    if (orderCount > 0) {
      const orders = await prisma.order.findMany({
        select: {
          id: true,
          publicOrderNumber: true,
          status: true,
          paymentStatus: true,
          totalMinor: true,
          createdAt: true,
          updatedAt: true,
        },
        orderBy: { createdAt: 'desc' }
      })
      console.log('Recent orders:', orders)
      
      // Check latest order events
      const latestOrder = orders[0]
      if (latestOrder) {
        const events = await prisma.orderEvent.findMany({
          where: { orderId: latestOrder.id },
          select: {
            id: true,
            eventType: true,
            actorUserId: true,
            createdAt: true,
          },
          orderBy: { createdAt: 'asc' }
        })
        console.log(`Events for order ${latestOrder.publicOrderNumber}:`, events)
        
        const items = await prisma.orderItem.findMany({
          where: { orderId: latestOrder.id },
          select: {
            id: true,
            productId: true,
            productNameSnapshot: true,
            quantity: true,
            lineTotalMinor: true,
          }
        })
        console.log(`Items for order ${latestOrder.publicOrderNumber}:`, items)
      }
    }
    
  } catch (error) {
    console.error('❌ Error checking order DB state:', error)
  } finally {
    await prisma.$disconnect()
  }
}

checkOrderDB()
