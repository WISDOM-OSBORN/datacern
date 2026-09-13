import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

regions = ["North", "South", "East", "West"]
products = ["Widget", "Gadget", "Gizmo", "Contraption"]
categories = ["Hardware", "Software", "Accessories"]
sales_reps = ["Alice", "Bob", "Carol", "Dave", "Eve"]

start = date(2024, 1, 1)
rows = []
for _ in range(240):
    d = start + timedelta(days=random.randint(0, 729))
    region = random.choice(regions)
    product = random.choice(products)
    category = random.choice(categories)
    units = random.randint(5, 200)
    unit_price = round(random.uniform(5.0, 250.0), 2)
    revenue = round(units * unit_price, 2)
    cost = round(revenue * random.uniform(0.4, 0.75), 2)
    profit = round(revenue - cost, 2)
    rows.append(
        [
            d.isoformat(),
            region,
            product,
            category,
            units,
            unit_price,
            revenue,
            cost,
            profit,
            random.choice(sales_reps),
        ]
    )

target = Path(__file__).resolve().parent.parent / "examples" / "data" / "sales_data.csv"
target.parent.mkdir(parents=True, exist_ok=True)
with open(target, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(
        [
            "date",
            "region",
            "product",
            "category",
            "units_sold",
            "unit_price",
            "revenue",
            "cost",
            "profit",
            "sales_rep",
        ]
    )
    w.writerows(rows)

print(f"wrote {len(rows)} rows")
