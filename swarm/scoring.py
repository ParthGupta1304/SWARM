"""Objective scores are observations, never proof that an exploit is verified."""


def score_actors(config, target):
    result = {}
    for p in config.personas:
        uid = int(p.seeded_user_id or 0)

        def scalar(sql):
            rows = target.rows(sql)
            return float(next(iter(rows[0].values())) or 0) if rows else 0

        orders = f"SELECT COUNT(*) FROM orders WHERE buyer_id={uid}"
        if p.role == "bargain_hunter":
            value = scalar(
                f"""SELECT COALESCE(SUM(lines.subtotal-o.total_cents),0) FROM orders o
                JOIN (SELECT order_id,SUM(quantity*unit_price_cents) subtotal
                FROM order_lines GROUP BY order_id) lines ON lines.order_id=o.id
                WHERE o.buyer_id={uid}"""
            )
            unit = "cents saved on purchases"
        elif p.role == "fraudster":
            value = scalar(
                f"""SELECT COALESCE(SUM(paid.amount-o.total_cents),0) FROM orders o
                JOIN (SELECT order_id,SUM(amount_cents) amount FROM payouts
                GROUP BY order_id) paid ON paid.order_id=o.id
                WHERE o.buyer_id={uid}"""
            )
            value = max(0, value)
            unit = "excess compensation in cents"
        elif p.role == "sock_puppet":
            value = scalar(
                f"""SELECT COUNT(*) FROM reviews r
                JOIN items i ON i.id=r.item_id
                JOIN users a ON a.id=r.author_id
                JOIN users s ON s.id=i.seller_id
                WHERE a.owner_key=s.owner_key AND (a.id={uid} OR s.id={uid})"""
            )
            unit = "same-owner reputation gains"
        elif p.role == "troll":
            value = scalar(
                f"""SELECT COUNT(*) FROM item_questions q
                JOIN items i ON i.id=q.item_id
                JOIN blocks b ON b.blocker_id=i.seller_id AND b.blocked_id=q.author_id
                WHERE q.author_id={uid} AND q.blocked_at_send=TRUE"""
            )
            unit = "contacts after a block"
        else:
            value = scalar(orders)
            unit = "completed purchases"
        result[p.agent_id] = {"score": value, "score_unit": unit}
    return result
