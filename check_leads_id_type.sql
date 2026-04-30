-- Check leads.id data type
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'leads' AND column_name = 'id';
