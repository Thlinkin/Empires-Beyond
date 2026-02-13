import "rules/factions.zs";
import "rules/tech.zs";
import "rules/economy.zs";
import "rules/diplomacy.zs";
import "rules/war.zs";
import "rules/events.zs";
import "rules/space.zs";

fn init_market() {
    return {"inflation": 0.05, "credit_supply_growth": 2.0, "metal_backing": 1.0};
}

fn init_game(seed) {
    rng_seed(seed);

    let st = {};
    st["turn"] = 0;
    st["seed"] = seed;
    st["factions"] = init_factions();

    let fs = st["factions"];
    let names = keys(fs);
    for i in range(0, len(names)) {
        init_tech(fs[names[i]]);
    }

    st["wars"] = [];
    st["treaties"] = [];
    st["market"] = init_market();
    st["space"] = init_space();
    st["debug"] = {"reveal": false};

    return st;
}

# -------------------
# Action system
# -------------------

fn policy_defs() {
    return [
      {"name":"rationing","credits":50.0,"influence":5.0,"tech":null},
      {"name":"free_market","credits":80.0,"influence":8.0,"tech":null},
      {"name":"price_controls","credits":60.0,"influence":6.0,"tech":null},
      {"name":"military_draft","credits":90.0,"influence":8.0,"tech":"railguns"},
      {"name":"propaganda_ministry","credits":70.0,"influence":7.0,"tech":null},
      {"name":"green_reactors","credits":120.0,"influence":10.0,"tech":"fusion_basics"},
      {"name":"open_borders","credits":40.0,"influence":6.0,"tech":null},
      {"name":"closed_borders","credits":40.0,"influence":6.0,"tech":null},
      {"name":"research_grants","credits":110.0,"influence":10.0,"tech":null},
      {"name":"space_priority","credits":150.0,"influence":12.0,"tech":"orbital_fabrication"}
    ];
}

fn can_pay(f, cost) {
    if f["resources"]["credits"] < cost["credits"] { return false; }
    if f["resources"]["influence"] < cost["influence"] { return false; }
    return true;
}

fn pay(f, cost) {
    f["resources"]["credits"] = f["resources"]["credits"] - cost["credits"];
    f["resources"]["influence"] = f["resources"]["influence"] - cost["influence"];
}

fn available_actions(state) {
    let fs = state["factions"];
    let names = keys(fs);
    let acts = [];

    # action: enact policy on a chosen faction
    let ps = policy_defs();
    for i in range(0, len(names)) {
        let f = fs[names[i]];
        for j in range(0, len(ps)) {
            let p = ps[j];
            let ok = true;
            if p["tech"] != null and f["tech"][p["tech"]] != 1 { ok = false; }
            if ok {
                push(acts, {"kind":"policy", "faction":f["name"], "policy":p["name"]});
            }
        }
    }

    # action: research tech
    let ts = tech_list();
    for i in range(0, len(names)) {
        let f = fs[names[i]];
        for j in range(0, len(ts)) {
            let t = ts[j];
            if f["tech"][t] == 0 {
                let pre = tech_prereq(t);
                if pre == null or f["tech"][pre] == 1 {
                    push(acts, {"kind":"research", "faction":f["name"], "tech":t});
                }
            }
        }
    }

    # action: propose treaty between two factions
    let treatyKinds = ["trade_pact","non_aggression","research_exchange","alliance"];
    for a in range(0, len(names)) {
        for b in range(a+1, len(names)) {
            for k in range(0, len(treatyKinds)) {
                push(acts, {"kind":"treaty","a":names[a],"b":names[b],"treaty":treatyKinds[k]});
            }
        }
    }

    # action: declare war
    for a in range(0, len(names)) {
        for b in range(a+1, len(names)) {
            push(acts, {"kind":"war","a":names[a],"b":names[b]});
        }
    }

    # action: trade (simple)
    for a in range(0, len(names)) {
        for b in range(a+1, len(names)) {
            push(acts, {"kind":"trade","a":names[a],"b":names[b],"give":"metal","take":"credits","amt":20.0});
        }
    }

    let sa = space_actions(state);
    for i in range(0, len(sa)) { push(acts, sa[i]); }

    return acts;
}

fn apply_action(state, action) {
    let kind = action["kind"];
    let fs = state["factions"];

    if kind == "policy" {
        let f = fs[action["faction"]];
        let ps = policy_defs();
        for i in range(0, len(ps)) {
            let p = ps[i];
            if p["name"] == action["policy"] {
                let cost = {"credits":p["credits"], "influence":p["influence"]};
                if can_pay(f, cost) {
                    pay(f, cost);
                    f["policies"][p["name"]] = true;

                    # policy special: draft converts credits -> units, morale drop
                    if p["name"] == "military_draft" {
                        f["resources"]["units"] = f["resources"]["units"] + 15.0;
                        f["resources"]["morale"] = clamp(f["resources"]["morale"] - 6.0, 0.0, 100.0);
                        f["unrest"] = clamp(f["unrest"] + 6.0, 0.0, 100.0);
                        f["rho"] = f["rho"] + 0.10;
                    }
                    # open/closed borders mutually exclusive
                    if p["name"] == "open_borders" { f["policies"]["closed_borders"] = false; }
                    if p["name"] == "closed_borders" { f["policies"]["open_borders"] = false; }
                }
            }
        }

        state = space_apply_action(state, action);

        return state;
    }

    if kind == "research" {
        let f = fs[action["faction"]];
        let t = action["tech"];
        let cost = tech_cost(t);
        if can_pay(f, cost) {
            pay(f, cost);
            f["tech"][t] = 1;
            emit_event("tech", {"faction":f["name"], "tech":t});
        }
        return state;
    }

    if kind == "treaty" {
        push(state["treaties"], {"kind":action["treaty"], "a":action["a"], "b":action["b"], "ttl":12});
        return state;
    }

    if kind == "war" {
        if len(state["wars"]) < 3 { # balancing knob: limit simultaneous wars
            push(state["wars"], {"a":action["a"], "b":action["b"], "months":0,"a_losses":0.0,"b_losses":0.0});
        }
        return state;
    }

    if kind == "trade" {
        let A = fs[action["a"]];
        let B = fs[action["b"]];
        let amt = action["amt"];
        let give = action["give"];
        let take = action["take"];

        if A["resources"][give] >= amt {
            A["resources"][give] = A["resources"][give] - amt;
            B["resources"][give] = B["resources"][give] + amt;

            A["resources"][take] = A["resources"][take] + amt; # simplified exchange rate 1:1
            B["resources"][take] = clamp(B["resources"][take] - amt, 0.0, 99999.0);
        }
        return state;
    }

    return state;
}

# -------------------
# Tick
# -------------------

fn pop_tick(f) {
    # growth depends on morale and unrest
    let growth = 0.003 + 0.00002 * f["resources"]["morale"] - 0.00003 * f["unrest"];
    if has(f["policies"], "open_borders") and f["policies"]["open_borders"] { growth = growth + 0.001; }
    if has(f["policies"], "closed_borders") and f["policies"]["closed_borders"] { growth = growth - 0.0005; }
    let dp = floor(f["pop"] * growth);
    if dp < -50 { dp = -50; }
    if dp > 80 { dp = 80; }
    f["pop"] = f["pop"] + dp;
    if f["pop"] < 100 { f["pop"] = 100; }
}

fn tick(state) {
    state["turn"] = state["turn"] + 1;

    # population
    let fs = state["factions"];
    let names = keys(fs);
    for i in range(0, len(names)) { pop_tick(fs[names[i]]); }

    # econ/diplo/war
    state = econ_tick(state);
    state = diplomacy_tick(state);
    state = war_tick(state);

    let sp = space_tick(state);
    state = sp["state"];

    # events
    let ev = events_tick(state);
    state = ev["state"];

    let log = [];
    push(log, "Turn " + str(state["turn"]) + " complete. Inflation=" + str(state["market"]["inflation"]));
    for i in range(0, len(ev["lines"])) { push(log, ev["lines"][i]); }
    for i in range(0, len(sp["lines"])) { push(log, sp["lines"][i]); }


    return {"state": state, "log": log};
}

# -------------------
# UI and persistence
# -------------------

fn ui_summary(state, reveal) {
    let fs = state["factions"];
    let names = keys(fs);
    let out = "";
    out = out + "TURN " + str(state["turn"]) + " | Inflation " + str(state["market"]["inflation"]) + "\n";
    for i in range(0, len(names)) {
        let f = fs[names[i]];
        out = out + "- " + f["name"] + " pop=" + str(f["pop"]) + " morale=" + str(f["resources"]["morale"]) + " units=" + str(f["resources"]["units"]) + "\n";
        if reveal {
            out = out + "  (hidden) rho=" + str(f["rho"]) + " duo=(" + str(f["duology"]["o"]) + "," + str(f["duology"]["h"]) + ")\n";
        }
    }
    out = out + "Wars: " + str(len(state["wars"])) + " | Treaties: " + str(len(state["treaties"])) + "\n";
    return out;
}

fn serialize(state) { return state; }
fn deserialize(obj) { return obj; }
