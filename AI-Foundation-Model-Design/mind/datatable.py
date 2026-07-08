"""
datatable  —  real analysis of a CSV / data table.  [answers you compute, not retrieve]

A spreadsheet is DATA, not prose. Memorizing its rows as text is useless — you can't
sum a column that way. This module loads a CSV as a typed table and answers data
questions by COMPUTING them exactly: counts, totals, averages, min/max, group-by,
top-N, filters, and a derived revenue (price × quantity). Every answer is exact and
verifiable, like the math tools.

    t = DataTable.from_csv(text, "sales.csv")
    t.answer("what is the total revenue?")     -> exact number
    t.answer("top 5 products by revenue")       -> ranked list
    t.answer("sales by category")               -> grouped totals
"""

from __future__ import annotations

import csv
import io
import re
import statistics

_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")


def _num(v):
    v = (v or "").strip().replace(",", "")
    return float(v) if _NUM.match(v) else None


def _fmt(x):
    if isinstance(x, float):
        return f"{x:,.2f}".rstrip("0").rstrip(".") if x != int(x) else f"{int(x):,}"
    return f"{x:,}" if isinstance(x, int) else str(x)


class DataTable:
    def __init__(self, name, headers, rows):
        self.name = name
        self.headers = headers                       # original column names
        self.rows = rows                             # list of dict {header: str}
        self.lower = {h.lower(): h for h in headers}  # lookup by lowercase
        # which columns are numeric (majority of values parse as numbers)
        self.numeric = []
        for h in headers:
            vals = [_num(r[h]) for r in rows]
            if sum(v is not None for v in vals) > 0.6 * max(1, len(rows)):
                self.numeric.append(h)

    # ---- loading ----------------------------------------------------------
    @classmethod
    def from_csv(cls, text, name="table"):
        text = text.lstrip("﻿")
        try:
            dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text), dialect)
        rows_raw = [r for r in reader if any(c.strip() for c in r)]
        if len(rows_raw) < 2:
            return None
        headers = [h.strip() or f"col{i}" for i, h in enumerate(rows_raw[0])]
        rows = []
        for r in rows_raw[1:]:
            if len(r) < len(headers):
                r = r + [""] * (len(headers) - len(r))
            rows.append({headers[i]: r[i].strip() for i in range(len(headers))})
        return cls(name, headers, rows)

    # ---- column resolution ------------------------------------------------
    @staticmethod
    def _stem(w):
        for suf, rep in (("ies", "y"), ("es", ""), ("s", "")):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                return w[:-len(suf)] + rep
        return w

    def _find_col(self, q, numeric_only=False, exclude=()):
        """Best column mentioned in the question — tolerant of plurals
        (categories→Category, cities→City, products→Product)."""
        pool = [h for h in (self.numeric if numeric_only else self.headers) if h not in exclude]
        toks = {self._stem(t) for t in re.findall(r"[a-z_]+", q.lower())}
        best, blen = None, 0
        for h in pool:
            hs = self._stem(h.lower())
            if hs in toks and len(hs) > blen:
                best, blen = h, len(hs)
        return best

    def _revenue(self):
        """A price*quantity measure if both columns exist (common for sales data)."""
        price = next((h for h in self.numeric if "price" in h.lower() or "amount" in h.lower()
                      or "sales" in h.lower() or "total" in h.lower()), None)
        qty = next((h for h in self.numeric if "quantity" in h.lower() or "qty" in h.lower()
                    or "units" in h.lower()), None)
        if price and qty:
            return [(_num(r[price]) or 0) * (_num(r[qty]) or 0) for r in self.rows], price, qty
        if price:
            return [_num(r[price]) or 0 for r in self.rows], price, None
        return None

    # ---- describe ---------------------------------------------------------
    def describe(self):
        return (f"Loaded “{self.name}”: {len(self.rows):,} rows × {len(self.headers)} columns.\n"
                f"Columns: {', '.join(self.headers)}.\n"
                f"Ask me things like: how many rows · total {self._numeric_example()} · "
                f"average {self._numeric_example()} · {self._group_example()} by "
                f"{self._cat_example()} · top 5 {self._cat_example()}.")

    def _numeric_example(self):
        return self.numeric[0].lower() if self.numeric else "a column"

    def _cat_example(self):
        cats = [h for h in self.headers if h not in self.numeric]
        return cats[0].lower() if cats else "a column"

    def _group_example(self):
        return "revenue" if self._revenue() else ("total " + self._numeric_example())

    # ---- the analyzer -----------------------------------------------------
    def answer(self, q):
        ql = q.lower().strip()

        # metadata
        if re.search(r"\b(columns?|fields?|headers?|schema|what.*(in|about).*(file|data|csv|table))\b", ql):
            return self.describe()
        if re.search(r"how many (rows|records|entries|orders|lines)|number of (rows|records)|"
                     r"row count|count.*(rows|records)", ql) and not self._find_col(ql, exclude=()):
            return f"{len(self.rows):,} rows."

        # "best-selling / top-selling / most popular <thing>" -> rank that column by units
        # sold (Quantity) if present, else by revenue, else by row count.
        if re.search(r"\bbest[- ]?selling|top[- ]?selling|most (?:popular|sold|purchased|"
                     r"bought)|highest[- ]?selling|\bselling\b|\bsold\b", ql):
            # the grouping noun named in the question (product/category/city…), else Product
            noun = re.sub(r"\b(best|top|selling|sold|most|popular|highest|purchased|bought|"
                          r"\d+|by|the|what|which|is|are)\b", " ", ql)
            group = self._find_col(noun) or self._find_col("product") \
                or next((h for h in self.headers if h not in self.numeric), None)
            if group:
                qty = next((h for h in self.numeric if re.search(r"quantity|qty|units|sold|count", h.lower())), None)
                if qty:
                    buckets = {}
                    for r in self.rows:
                        buckets[r[group] or "(blank)"] = buckets.get(r[group] or "(blank)", 0) + (_num(r[qty]) or 0)
                    measure = f"units ({qty})"
                else:
                    rev = self._revenue()
                    buckets = {}
                    for i, r in enumerate(self.rows):
                        key = r[group] or "(blank)"
                        buckets[key] = buckets.get(key, 0) + (rev[0][i] if rev else 1)
                    measure = "revenue" if rev else "orders"
                rank = re.search(r"top\s+(\d+)", ql)
                n = int(rank.group(1)) if rank else 1
                top = sorted(buckets.items(), key=lambda kv: -kv[1])[:n]
                if n == 1:
                    k, v = top[0]
                    return f"Best-selling {group}: {k} — {_fmt(v)} {measure}."
                return f"Top {n} {group} by {measure}:\n" + "\n".join(f"  • {k}: {_fmt(v)}" for k, v in top)

        wants_revenue = bool(re.search(r"\b(revenue|sales|income|earnings|turnover|total sales)\b", ql))

        # aggregation intent
        agg = None
        if re.search(r"\b(average|mean|avg)\b", ql): agg = "avg"
        elif re.search(r"\b(sum|total|combined|altogether)\b", ql) or wants_revenue: agg = "sum"
        elif re.search(r"\b(max|maximum|highest|largest|biggest|most expensive|top|best)\b", ql): agg = "max"
        elif re.search(r"\b(min|minimum|lowest|smallest|cheapest)\b", ql): agg = "min"
        elif re.search(r"\b(median)\b", ql): agg = "median"
        elif re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", ql): agg = "count"

        group = self._group_col(ql)

        # when ranking groups ("top 5 X by Y"), sum the measure per group unless the
        # user explicitly asked for an average — "top/best/highest" are RANKING words,
        # not an instruction to take the max of each group.
        group_agg = "avg" if agg == "avg" else "sum"

        # top-N ranking:  "top 5 products by revenue", "which city has most orders"
        m = re.search(r"top\s+(\d+)", ql)
        topn = int(m.group(1)) if m else (5 if re.search(r"\btop\b|\bbest\b|\branking\b|\brank\b", ql) else None)
        if group and (topn or re.search(r"\b(which|what)\b.*\b(most|highest|top|best|largest)\b", ql)):
            return self._grouped(group, ql, wants_revenue, group_agg, rank=topn or 1)

        # grouped aggregate:  "sales by category", "average price per city"
        if group:
            return self._grouped(group, ql, wants_revenue, group_agg, rank=None)

        # single-column / whole-table aggregate
        if wants_revenue:
            rev = self._revenue()
            if rev:
                vals, price, qty = rev
                if agg in (None, "sum"):
                    return (f"Total revenue = {_fmt(sum(vals))}"
                            + (f"  (sum of {price} × {qty} over {len(vals):,} rows)." if qty
                               else f"  (sum of {price})."))
                return self._reduce(agg, vals, f"revenue")

        col = self._find_col(ql, numeric_only=(agg not in (None, "count")))
        if agg == "count":
            fcol, fval = self._filter(ql)
            if fcol:
                n = sum(1 for r in self.rows if r[fcol].lower() == fval.lower())
                return f"{n:,} rows where {fcol} = {fval}."
            c = self._find_col(ql)
            if c and c not in self.numeric:
                return f"{len({r[c] for r in self.rows}):,} distinct values in {c}."
            return f"{len(self.rows):,} rows."
        if agg and col:
            vals = [v for v in (_num(r[col]) for r in self.rows) if v is not None]
            if vals:
                return self._reduce(agg, vals, col)

        # "what products/categories are there" -> distinct list
        c = self._find_col(ql)
        if c and re.search(r"\b(what|which|list|show|distinct|unique|kinds?|types?)\b", ql):
            vals = sorted({r[c] for r in self.rows if r[c]})
            head = ", ".join(vals[:20]) + (f" … (+{len(vals)-20} more)" if len(vals) > 20 else "")
            return f"{len(vals)} distinct {c}: {head}"
        return None                                  # not a data question this table can answer

    # ---- helpers ----------------------------------------------------------
    def _group_col(self, ql):
        # "top 5 PRODUCTS by revenue" -> the group is the noun after "top N"
        m = re.search(r"top\s+\d+\s+([a-z ]+?)\s+by\b", ql) or re.search(r"top\s+\d+\s+([a-z]+)", ql)
        if m:
            c = self._find_col(m.group(1))
            if c:
                return c
        # "... by/per X" — but skip when X is really the measure (revenue/price/etc.)
        m = re.search(r"\b(?:by|per|for each|across|grouped by)\s+([a-z ]+)", ql)
        if m and not re.search(r"\b(revenue|sales|income|price|amount|total|value)\b", m.group(1)):
            c = self._find_col(m.group(1))
            if c:
                return c
        # "which city / what category …" implies grouping by that column
        m = re.search(r"\b(?:which|what|each)\s+([a-z]+)", ql)
        if m:
            c = self._find_col(m.group(1))
            if c and c not in self.numeric:
                return c
        return None

    def _filter(self, ql):
        for h in self.headers:
            if h in self.numeric:
                continue
            for val in {r[h] for r in self.rows}:
                if val and re.search(r"\b" + re.escape(val.lower()) + r"\b", ql):
                    return h, val
        return None, None

    def _measure(self, ql, wants_revenue):
        if wants_revenue:
            rev = self._revenue()
            if rev:
                return rev[0], "revenue"
        col = self._find_col(ql, numeric_only=True)
        if col:
            return [_num(r[col]) or 0 for r in self.rows], col
        # default measure: count
        return None, None

    def _grouped(self, group, ql, wants_revenue, agg, rank):
        vals, mname = self._measure(ql, wants_revenue)
        buckets = {}
        for i, r in enumerate(self.rows):
            key = r[group] or "(blank)"
            if vals is None:                         # counting rows per group
                buckets[key] = buckets.get(key, 0) + 1
            else:
                buckets.setdefault(key, []).append(vals[i])
        if vals is None:
            scored = [(k, v) for k, v in buckets.items()]
            label = "count"
        else:
            fn = {"sum": sum, "avg": lambda x: statistics.mean(x),
                  "max": max, "min": min, "median": statistics.median}.get(agg, sum)
            scored = [(k, fn(v)) for k, v in buckets.items()]
            label = {"sum": "total", "avg": "average", "max": "max", "min": "min"}.get(agg, "total")
        scored.sort(key=lambda kv: -kv[1])
        shown = scored[:rank] if rank else scored[:12]
        head = f"{label.capitalize()} {mname or 'rows'} by {group}:"
        lines = [f"  • {k}: {_fmt(v)}" for k, v in shown]
        if rank == 1:
            k, v = scored[0]
            if vals is None:
                return f"{k} — with {_fmt(v)} rows, the most of any {group}."
            return f"{k} — with {label} {mname} of {_fmt(v)} (the highest by {group})."
        more = f"\n  … (+{len(scored)-len(shown)} more)" if len(scored) > len(shown) else ""
        return head + "\n" + "\n".join(lines) + more

    @staticmethod
    def _reduce(agg, vals, name):
        if agg == "avg":
            return f"Average {name} = {_fmt(statistics.mean(vals))}  (over {len(vals):,} rows)."
        if agg == "sum":
            return f"Total {name} = {_fmt(sum(vals))}  (sum over {len(vals):,} rows)."
        if agg == "max":
            return f"Maximum {name} = {_fmt(max(vals))}."
        if agg == "min":
            return f"Minimum {name} = {_fmt(min(vals))}."
        if agg == "median":
            return f"Median {name} = {_fmt(statistics.median(vals))}."
        return f"{name}: {_fmt(sum(vals))}"
