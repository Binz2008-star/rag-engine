-- Remove foreign key constraint from order_items table
-- This is needed because we removed the Product model from the schema

ALTER TABLE order_items DROP CONSTRAINT order_items_product_id_fkey;
