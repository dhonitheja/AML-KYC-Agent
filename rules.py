"""Illustrative review triggers for synthetic USD transactions, not calibrated bank policy."""
def assess(row, minute_count, hour_count, history):
    amount = row["amount_cents"]
    debit = row["direction"] == "debit"
    credits = [item for item in history if item["direction"] == "credit"]
    inflows = sum(item["amount_cents"] for item in credits)
    hits = []

    def hit(name, points, evidence):
        hits.append(dict(rule=name, points=points, evidence=evidence))

    if debit and inflows and 75 * inflows <= amount * 100 <= 125 * inflows:
        hit("rapid_pass_through", 65, [x["id"] for x in credits] + [row["id"]])
    if amount >= 10_000_000:
        hit("large_single_transfer", 35, [row["id"]])
    if row["channel"].lower() == "cash" and amount >= 500_000:
        hit("large_cash_activity", 25, [row["id"]])
    if minute_count >= 10:
        hit("minute_velocity", 35, [row["id"], f"{minute_count} transactions in 60s"])
    if hour_count >= 40:
        hit("hour_velocity", 25, [row["id"], f"{hour_count} transactions in 1h"])
    matches = [x for x in history if (x["direction"], x["amount_cents"], x["channel"]) ==
               (row["direction"], amount, row["channel"])]
    if len(matches) >= 2:
        hit("repeated_amount", 30, [x["id"] for x in matches[-2:]] + [row["id"]])
    parties = {x["counterparty"] for x in credits}
    if debit and len(parties) >= 4:
        hit("multiple_credit_sources", 30, [x["id"] for x in credits] + [row["id"]])
    score = min(100, sum(h["points"] for h in hits))
    return dict(transaction_id=row["id"], case_id=row["case_id"], run_id=row["run_id"],
                version="v1", score=score, alert=score >= 60, rules=hits)
