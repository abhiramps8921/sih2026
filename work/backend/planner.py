import math
from datetime import timedelta
from .catalog import PLACES, BY_ID, TEMPLATE_STOPS, slh_score

def travel_minutes(a, b):
    # Great-circle distance inflated for street indirectness; not live road routing.
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = lat2 - lat1
    dlng = math.radians(b["lng"] - a["lng"])
    distance = 6371 * 2 * math.asin(min(1, math.sqrt(math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2)))
    return max(10, math.ceil(distance * 1.3 / 4 * 60))

def time_label(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"

def generate_plan(preferences):
    budget = preferences.budget
    chosen_ids = TEMPLATE_STOPS.get(preferences.template_id, [])
    candidates = [p for p in PLACES if not preferences.min_slh or (slh_score(p["slh"]) or 0) >= preferences.min_slh]
    candidates.sort(key=lambda p: (p["id"] in chosen_ids, p["category"] in preferences.interests, slh_score(p["slh"])), reverse=True)
    used, days, warnings = set(), [], []
    target = {"relaxed":3, "balanced":4, "packed":5}[preferences.pace]
    for day in range(preferences.days):
        clock, spent, stops = 9 * 60, 0, []
        previous = {"lat":9.9657, "lng":76.242}
        remaining = [p for p in candidates if p["id"] not in used]
        for _ in range(target):
            feasible = []
            for p in remaining:
                travel = travel_minutes(previous, p)
                start = max(clock + travel, p["opens"] * 60)
                # Reserve food + local transport per day, outside each stop's cost.
                if spent + p["cost"] + 400 > budget or start + p["duration"] > min(18*60, p["closes"]*60):
                    continue
                preference = (80 if p["id"] in chosen_ids else 0) + (40 if p["category"] in preferences.interests else 0)
                rank = preference + (slh_score(p["slh"]) or 0)/10 - travel/5 - max(0,start-clock-travel)/10
                feasible.append((rank,p,travel,start))
            if not feasible:
                break
            _, picked, travel, start = max(feasible, key=lambda item:item[0])
            stops.append(dict(id=f"d{day+1}-{picked['id']}",place=picked,start=time_label(start),end=time_label(start+picked["duration"]),travel_minutes=travel,completed=False))
            used.add(picked["id"])
            remaining = [p for p in remaining if p["id"] != picked["id"]]
            spent += picked["cost"]
            clock = start + picked["duration"] + 20
            previous = picked
        if not stops:
            raise ValueError("No feasible stops fit this plan. Increase your budget or lower the SLH filter.")
        if len(stops) < target:
            warnings.append(f"Day {day+1} has fewer stops to respect your budget and available time.")
        days.append(dict(day=day+1,date=str(preferences.start_date+timedelta(days=day)),stops=stops,cost=spent+400))
    return dict(title=preferences.title or "Your little Kochi escape",city="Kochi",days=days,
                preferences=preferences.model_dump(mode="json"),total_cost=sum(d["cost"] for d in days),
                warnings=warnings,method="Rule-based local planner",routing="Walking estimates; lines are not road directions",
                cost_note="Per person. Includes ₹400/day food and local transport allowance; excludes stay and travel to Kochi. Venue prices and hours are sample estimates.")
