SELECT order_id, status, COUNT(*) as count 
FROM payment_attempts 
WHERE order_id LIKE 'cmnh%' 
GROUP BY order_id, status 
ORDER BY count DESC;
