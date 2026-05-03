#!/usr/bin/env tsx

/**
 * Test Environment Setup Script
 * 
 * This script creates an isolated testing environment with sample data
 * for user testing of the order management system.
 */

import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

interface TestSeller {
  email: string;
  password: string;
  brandName: string;
  slug: string;
  currency: string;
}

interface TestProduct {
  name: string;
  slug: string;
  description: string;
  priceMinor: number;
  currency: string;
  stockQuantity: number;
  category: string;
}

interface TestCustomer {
  name: string;
  phone: string;
  addressText: string;
}

const TEST_SELLERS: TestSeller[] = [
  {
    email: 'seller1@test.com',
    password: 'TestSeller123!',
    brandName: 'Tech Gadgets Plus',
    slug: 'tech-gadgets-plus',
    currency: 'USD'
  },
  {
    email: 'seller2@test.com', 
    password: 'TestSeller123!',
    brandName: 'Fashion Forward',
    slug: 'fashion-forward',
    currency: 'USD'
  },
  {
    email: 'seller3@test.com',
    password: 'TestSeller123!',
    brandName: 'Home & Living',
    slug: 'home-living',
    currency: 'USD'
  }
];

const TEST_PRODUCTS: TestProduct[] = [
  // Electronics for Tech Gadgets Plus
  {
    name: 'Wireless Phone Charger',
    slug: 'wireless-phone-charger',
    description: 'Fast wireless charging pad compatible with all smartphones',
    priceMinor: 2999,
    currency: 'USD',
    stockQuantity: 150,
    category: 'electronics'
  },
  {
    name: 'Bluetooth Earbuds Pro',
    slug: 'bluetooth-earbuds-pro',
    description: 'Premium noise-cancelling wireless earbuds',
    priceMinor: 7999,
    currency: 'USD',
    stockQuantity: 75,
    category: 'electronics'
  },
  {
    name: 'Phone Case Premium',
    slug: 'phone-case-premium',
    description: 'Durable protective case with kickstand',
    priceMinor: 1999,
    currency: 'USD',
    stockQuantity: 200,
    category: 'electronics'
  },
  {
    name: 'USB-C Cable Set',
    slug: 'usb-c-cable-set',
    description: '3-pack of durable USB-C charging cables',
    priceMinor: 2499,
    currency: 'USD',
    stockQuantity: 300,
    category: 'electronics'
  },
  {
    name: 'Portable Power Bank',
    slug: 'portable-power-bank',
    description: '10000mAh portable charger with fast charging',
    priceMinor: 4999,
    currency: 'USD',
    stockQuantity: 100,
    category: 'electronics'
  },

  // Clothing for Fashion Forward
  {
    name: 'Classic Cotton T-Shirt',
    slug: 'classic-cotton-tshirt',
    description: 'Comfortable 100% cotton t-shirt in various colors',
    priceMinor: 2499,
    currency: 'USD',
    stockQuantity: 500,
    category: 'clothing'
  },
  {
    name: 'Denim Jacket',
    slug: 'denim-jacket',
    description: 'Classic fit denim jacket with modern styling',
    priceMinor: 7999,
    currency: 'USD',
    stockQuantity: 150,
    category: 'clothing'
  },
  {
    name: 'Athletic Leggings',
    slug: 'athletic-leggings',
    description: 'High-performance workout leggings',
    priceMinor: 3499,
    currency: 'USD',
    stockQuantity: 250,
    category: 'clothing'
  },
  {
    name: 'Casual Hoodie',
    slug: 'casual-hoodie',
    description: 'Comfortable fleece hoodie with kangaroo pocket',
    priceMinor: 5999,
    currency: 'USD',
    stockQuantity: 200,
    category: 'clothing'
  },
  {
    name: 'Wool Beanie Hat',
    slug: 'wool-beanie-hat',
    description: 'Warm wool blend beanie for cold weather',
    priceMinor: 1999,
    currency: 'USD',
    stockQuantity: 300,
    category: 'clothing'
  },

  // Home & Living for Home & Living
  {
    name: 'Ceramic Plant Pot Set',
    slug: 'ceramic-plant-pot-set',
    description: 'Set of 3 decorative ceramic plant pots',
    priceMinor: 3499,
    currency: 'USD',
    stockQuantity: 100,
    category: 'home'
  },
  {
    name: 'Kitchen Knife Set',
    slug: 'kitchen-knife-set',
    description: '5-piece stainless steel knife set with block',
    priceMinor: 9999,
    currency: 'USD',
    stockQuantity: 50,
    category: 'home'
  },
  {
    name: 'Throw Pillows Set',
    slug: 'throw-pillows-set',
    description: 'Set of 2 decorative throw pillows with covers',
    priceMinor: 4499,
    currency: 'USD',
    stockQuantity: 150,
    category: 'home'
  },
  {
    name: 'Wall Art Canvas',
    slug: 'wall-art-canvas',
    description: 'Modern abstract wall art canvas print',
    priceMinor: 6999,
    currency: 'USD',
    stockQuantity: 75,
    category: 'home'
  },
  {
    name: 'Bamboo Cutting Board',
    slug: 'bamboo-cutting-board',
    description: 'Eco-friendly bamboo cutting board with juice groove',
    priceMinor: 2999,
    currency: 'USD',
    stockQuantity: 200,
    category: 'home'
  }
];

const TEST_CUSTOMERS: TestCustomer[] = [
  {
    name: 'John Smith',
    phone: '+15551234567',
    addressText: '123 Main St, New York, NY 10001'
  },
  {
    name: 'Sarah Johnson',
    phone: '+15552345678',
    addressText: '456 Oak Ave, Los Angeles, CA 90001'
  },
  {
    name: 'Mike Wilson',
    phone: '+15553456789',
    addressText: '789 Pine Rd, Chicago, IL 60601'
  },
  {
    name: 'Emily Brown',
    phone: '+15554567890',
    addressText: '321 Elm St, Houston, TX 77001'
  },
  {
    name: 'David Lee',
    phone: '+15555678901',
    addressText: '654 Maple Dr, Phoenix, AZ 85001'
  }
];

async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, 12);
}

async function createTestSellers(): Promise<Map<string, string>> {
  console.log('Creating test sellers...');
  const sellerIdMap = new Map<string, string>();

  for (const sellerData of TEST_SELLERS) {
    // Create user account
    const hashedPassword = await hashPassword(sellerData.password);
    
    const user = await prisma.user.create({
      data: {
        email: sellerData.email,
        passwordHash: hashedPassword,
        fullName: sellerData.brandName,
        role: 'SELLER',
        isActive: true
      }
    });

    // Create seller profile
    const seller = await prisma.seller.create({
      data: {
        ownerUserId: user.id,
        brandName: sellerData.brandName,
        slug: sellerData.slug,
        currency: sellerData.currency,
        status: 'ACTIVE'
      }
    });

    sellerIdMap.set(sellerData.slug, seller.id);
    console.log(`Created seller: ${sellerData.brandName} (${sellerData.email})`);
  }

  return sellerIdMap;
}

async function createTestProducts(sellerIdMap: Map<string, string>): Promise<Map<string, string>> {
  console.log('Creating test products...');
  const productIdMap = new Map<string, string>();

  const sellerProducts = new Map<string, TestProduct[]>();
  
  // Assign products to sellers by category
  TEST_PRODUCTS.forEach(product => {
    let sellerSlug: string;
    
    if (product.category === 'electronics') {
      sellerSlug = 'tech-gadgets-plus';
    } else if (product.category === 'clothing') {
      sellerSlug = 'fashion-forward';
    } else {
      sellerSlug = 'home-living';
    }
    
    if (!sellerProducts.has(sellerSlug)) {
      sellerProducts.set(sellerSlug, []);
    }
    sellerProducts.get(sellerSlug)!.push(product);
  });

  for (const [sellerSlug, products] of sellerProducts) {
    const sellerId = sellerIdMap.get(sellerSlug);
    if (!sellerId) continue;

    for (const productData of products) {
      const product = await prisma.product.create({
        data: {
          sellerId,
          name: productData.name,
          slug: productData.slug,
          description: productData.description,
          priceMinor: productData.priceMinor,
          currency: productData.currency,
          stockQuantity: productData.stockQuantity,
          isActive: true
        }
      });

      productIdMap.set(productData.slug, product.id);
      console.log(`Created product: ${productData.name} for ${sellerSlug}`);
    }
  }

  return productIdMap;
}

async function createTestCustomers(sellerIdMap: Map<string, string>): Promise<Map<string, string>> {
  console.log('Creating test customers...');
  const customerIdMap = new Map<string, string>();

  // Create customers for each seller
  for (const [sellerSlug, sellerId] of sellerIdMap) {
    for (let i = 0; i < TEST_CUSTOMERS.length; i++) {
      const customerData = TEST_CUSTOMERS[i];
      
      const customer = await prisma.customer.create({
        data: {
          sellerId,
          name: `${customerData.name} - ${sellerSlug}`,
          phone: `${i + 1}${customerData.phone.substring(1)}`, // Make unique per seller
          addressText: customerData.addressText
        }
      });

      customerIdMap.set(`${sellerSlug}-${i}`, customer.id);
    }
  }

  console.log(`Created ${TEST_CUSTOMERS.length * TEST_SELLERS.length} test customers`);
  return customerIdMap;
}

async function createSampleOrders(
  sellerIdMap: Map<string, string>,
  productIdMap: Map<string, string>,
  customerIdMap: Map<string, string>
): Promise<void> {
  console.log('Creating sample orders...');

  const orderStatuses = ['PENDING', 'CONFIRMED', 'PACKED', 'OUT_FOR_DELIVERY', 'DELIVERED'];
  const paymentStatuses = ['PENDING', 'PAID', 'FAILED'];

  for (const [sellerSlug, sellerId] of sellerIdMap) {
    // Create 5-10 sample orders per seller
    const orderCount = Math.floor(Math.random() * 6) + 5;
    
    for (let i = 0; i < orderCount; i++) {
      const customerId = customerIdMap.get(`${sellerSlug}-${i % TEST_CUSTOMERS.length}`)!;
      
      // Get 1-3 random products for this seller
      const sellerProducts = Array.from(productIdMap.entries())
        .filter(([slug]) => {
          const product = TEST_PRODUCTS.find(p => p.slug === slug);
          return product && (
            (product.category === 'electronics' && sellerSlug === 'tech-gadgets-plus') ||
            (product.category === 'clothing' && sellerSlug === 'fashion-forward') ||
            (product.category === 'home' && sellerSlug === 'home-living')
          );
        });
      
      if (sellerProducts.length === 0) continue;

      const selectedProducts = sellerProducts
        .sort(() => Math.random() - 0.5)
        .slice(0, Math.floor(Math.random() * 3) + 1);

      const totalMinor = selectedProducts.reduce((sum, [_, productId]) => {
        const product = TEST_PRODUCTS.find(p => productIdMap.get(p.slug) === productId);
        return sum + (product?.priceMinor || 0);
      }, 0);

      const order = await prisma.order.create({
        data: {
          sellerId,
          customerId,
          publicOrderNumber: `TEST-${sellerSlug.toUpperCase().substring(0, 3)}-${String(i + 1).padStart(3, '0')}`,
          subtotalMinor: totalMinor,
          deliveryFeeMinor: 0,
          totalMinor,
          currency: 'USD',
          source: 'TEST_DATA',
          notes: `Sample order #${i + 1} for testing`,
          status: orderStatuses[Math.floor(Math.random() * orderStatuses.length)] as any,
          paymentStatus: paymentStatuses[Math.floor(Math.random() * paymentStatuses.length)] as any,
          paymentType: Math.random() > 0.5 ? 'CASH' : 'CASH_ON_DELIVERY'
        }
      });

      // Create order items
      for (const [productSlug, productId] of selectedProducts) {
        const product = TEST_PRODUCTS.find(p => p.slug === productSlug)!;
        
        await prisma.orderItem.create({
          data: {
            orderId: order.id,
            productId,
            productNameSnapshot: product.name,
            unitPriceMinor: product.priceMinor,
            quantity: 1,
            lineTotalMinor: product.priceMinor
          }
        });
      }

      console.log(`Created sample order: ${order.publicOrderNumber} for ${sellerSlug}`);
    }
  }
}

async function main(): Promise<void> {
  try {
    console.log('Setting up test environment...\n');

    // Clean existing test data (optional - uncomment if needed)
    // console.log('Cleaning existing test data...');
    // await prisma.order.deleteMany({ where: { source: 'TEST_DATA' } });
    // await prisma.customer.deleteMany({ where: { seller: { brandName: { contains: 'Test' } } } });
    // await prisma.product.deleteMany({ where: { name: { contains: 'Test' } } });
    // await prisma.seller.deleteMany({ where: { brandName: { contains: 'Test' } } });

    // Create test data
    const sellerIdMap = await createTestSellers();
    const productIdMap = await createTestProducts(sellerIdMap);
    const customerIdMap = await createTestCustomers(sellerIdMap);
    await createSampleOrders(sellerIdMap, productIdMap, customerIdMap);

    console.log('\nTest environment setup complete!');
    console.log('\nTest Seller Accounts:');
    TEST_SELLERS.forEach(seller => {
      console.log(`  ${seller.brandName}: ${seller.email} / ${seller.password}`);
    });

    console.log('\nTest Data Summary:');
    console.log(`  Sellers: ${TEST_SELLERS.length}`);
    console.log(`  Products: ${TEST_PRODUCTS.length}`);
    console.log(`  Customers: ${TEST_CUSTOMERS.length * TEST_SELLERS.length}`);
    console.log(`  Sample Orders: Created per seller`);

  } catch (error) {
    console.error('Error setting up test environment:', error);
    throw error;
  } finally {
    await prisma.$disconnect();
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
