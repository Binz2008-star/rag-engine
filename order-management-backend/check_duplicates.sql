SELECT order_id, status, COUNT(*) as count
FROM payment_attempts
GROUP BY order_id, status
HAVING count > 1;
