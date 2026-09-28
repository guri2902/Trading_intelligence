from collections import defaultdict

def previous_day_levels(rows):
    days=defaultdict(list)
    for r in rows: days[r["timestamp"].date()].append(r)
    ordered=sorted(days)
    out={}
    for i,d in enumerate(ordered):
        if i==0: out[d.isoformat()]={"pdh":None,"pdl":None,"pdc":None}
        else:
            prev=days[ordered[i-1]]
            out[d.isoformat()]={"pdh":max(float(x["high"]) for x in prev),
                                "pdl":min(float(x["low"]) for x in prev),
                                "pdc":float(prev[-1]["close"])}
    return out

def current_day_levels(rows):
    days=defaultdict(list)
    for r in rows: days[r["timestamp"].date()].append(r)
    return {d.isoformat(): {
        "open":float(rs[0]["open"]),
        "high":max(float(x["high"]) for x in rs),
        "low":min(float(x["low"]) for x in rs),
        "close":float(rs[-1]["close"])
    } for d,rs in days.items()}

def distance_from_level(price, level):
    return None if level is None else price-level

def percent_distance_from_level(price, level):
    return None if level in (None,0) else (price-level)/level
