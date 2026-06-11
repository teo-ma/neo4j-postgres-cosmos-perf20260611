#!/usr/bin/env python3
"""Generate a synthetic social-network graph shared by all three databases.

Outputs into ./data/:
  - persons.csv   : id,name,age,city
  - knows.csv     : src,dst,since
The same files are loaded into Neo4j, PostgreSQL and Cosmos DB so the
benchmark compares identical data.
"""
import csv
import os
import random
import sys

NUM_NODES = int(os.environ.get("NUM_NODES", "100000"))
NUM_EDGES = int(os.environ.get("NUM_EDGES", "1000000"))
SEED = int(os.environ.get("SEED", "42"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CITIES = ["Seattle", "Austin", "Boston", "Denver", "Miami", "Chicago",
          "Portland", "Atlanta", "Dallas", "Phoenix"]
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley",
         "Jamie", "Drew", "Quinn", "Avery", "Parker"]
LAST = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Miller", "Davis",
        "Wilson", "Moore", "Clark", "Walker", "Young"]


def main():
    random.seed(SEED)
    os.makedirs(DATA_DIR, exist_ok=True)

    print(f"Generating {NUM_NODES} persons -> persons.csv")
    with open(os.path.join(DATA_DIR, "persons.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "age", "city"])
        for i in range(NUM_NODES):
            name = f"{random.choice(FIRST)} {random.choice(LAST)}"
            age = random.randint(18, 80)
            city = random.choice(CITIES)
            w.writerow([i, name, age, city])

    print(f"Generating {NUM_EDGES} KNOWS edges -> knows.csv")
    # Skewed degree distribution: a few hubs, most low-degree.
    seen = set()
    written = 0
    with open(os.path.join(DATA_DIR, "knows.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst", "since"])
        while written < NUM_EDGES:
            src = random.randint(0, NUM_NODES - 1)
            # 20% of edges target low-id "hub" nodes to create deep paths
            if random.random() < 0.2:
                dst = random.randint(0, min(999, NUM_NODES - 1))
            else:
                dst = random.randint(0, NUM_NODES - 1)
            if src == dst:
                continue
            key = (src, dst)
            if key in seen:
                continue
            seen.add(key)
            since = random.randint(2005, 2025)
            w.writerow([src, dst, since])
            written += 1
            if written % 200000 == 0:
                print(f"  {written}/{NUM_EDGES} edges")

    print("Done. Files in", DATA_DIR)


if __name__ == "__main__":
    sys.exit(main())
