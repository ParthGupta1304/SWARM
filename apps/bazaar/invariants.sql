-- Deterministic Bazaar oracle queries. Each returned row is a finding candidate.

-- invariant: E1 | critical | Units sold exceed initial inventory
SELECT 'E1' AS bug_id, item_id, SUM(quantity) AS sold, MAX(initial_inventory) AS initial_inventory
FROM order_lines
JOIN items ON items.id = order_lines.item_id
GROUP BY item_id
HAVING SUM(quantity) > MAX(initial_inventory);

-- invariant: E2 | high | One account redeemed the same coupon more than once
SELECT 'E2' AS bug_id, user_id, coupon_id, COUNT(*) AS redemptions
FROM coupon_redemptions
GROUP BY user_id, coupon_id
HAVING COUNT(*) > 1;

-- invariant: E4 | critical | An order received both a refund and a dispute credit
SELECT 'E4' AS bug_id, order_id, COUNT(*) AS payouts, SUM(amount_cents) AS total_paid
FROM payouts
GROUP BY order_id
HAVING COUNT(*) > 1;

-- invariant: E5 | high | A seller reviewed their own listing
SELECT 'E5' AS bug_id, reviews.id AS review_id, reviews.item_id, reviews.author_id
FROM reviews
JOIN items ON items.id = reviews.item_id
WHERE reviews.author_id = items.seller_id;

-- invariant: E7 | high | A blocked buyer contacted the seller by an item question
SELECT 'E7' AS bug_id, item_questions.id AS question_id, item_questions.item_id, item_questions.author_id
FROM item_questions
JOIN items ON items.id = item_questions.item_id
JOIN blocks ON blocks.blocker_id = items.seller_id AND blocks.blocked_id = item_questions.author_id
WHERE item_questions.created_at >= blocks.created_at;

-- invariant: S2 | medium | No cart may contain a zero or negative line quantity
SELECT 'S2' AS bug_id, id AS cart_item_id, user_id, item_id, quantity
FROM cart_items
WHERE quantity <= 0;
