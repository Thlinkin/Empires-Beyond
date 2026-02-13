import "rules/math_system.zs";

fn habitat_make(name, owner) {
    if name == "Orbital Ring" {
        return {"name":name,"owner":owner,"mass_cap":500.0,"mass_used":100.0,"power_gen":220.0,"power_use":180.0,
                "o2":60.0,"water":60.0,"waste":10.0,"rad":120.0,"morale":70.0,"status":"ok"};
    }
    if name == "Lunar Vault" {
        return {"name":name,"owner":owner,"mass_cap":900.0,"mass_used":150.0,"power_gen":180.0,"power_use":170.0,
                "o2":90.0,"water":90.0,"waste":8.0,"rad":60.0,"morale":65.0,"status":"ok"};
    }
    # Mars Dome
    return {"name":name,"owner":owner,"mass_cap":1400.0,"mass_used":220.0,"power_gen":260.0,"power_use":240.0,
            "o2":105.0,"water":105.0,"waste":12.0,"rad":180.0,"morale":60.0,"status":"ok"};
}

fn init_space() {
    return {"unlocked": false, "habitats": {}, "budget_monthly": 0.0, "supply_queue": [], "postmortems": []};
}

fn travel_time(hab) {
    if hab == "Orbital Ring" { return 1; }
    if hab == "Lunar Vault" { return 2; }
    return 6;
}

fn shipment_make(hab, payload, amt, eta) {
    return {"hab":hab, "payload":payload, "amt":amt, "eta":eta};
}

fn space_unlock_if_ready(state) {
    if state["space"]["unlocked"] { return state; }
    let fs = state["factions"];
    let names = keys(fs);
    for i in range(0, len(names)) {
        if fs[names[i]]["tech"]["orbital_fabrication"] == 1 {
            state["space"]["unlocked"] = true;
            emit_event("space_unlock", {"by":names[i]});
        }
    }
    return state;
}

fn space_actions(state) {
    let acts = [];
    if !state["space"]["unlocked"] { return acts; }

    let fs = state["factions"];
    let names = keys(fs);

    # build habitats (one per faction max each for v1)
    let habs = ["Orbital Ring","Lunar Vault","Mars Dome"];
    for i in range(0, len(names)) {
        for j in range(0, len(habs)) {
            push(acts, {"kind":"build_hab","faction":names[i],"hab":habs[j]});
        }
        push(acts, {"kind":"set_space_budget","faction":names[i],"amt":100.0});
    }

    # shipments
    let hs = keys(state["space"]["habitats"]);
    for i in range(0, len(hs)) {
        let h = hs[i];
        push(acts, {"kind":"ship","hab":h,"payload":"water","amt":20.0});
        push(acts, {"kind":"ship","hab":h,"payload":"food","amt":20.0});
        push(acts, {"kind":"ship","hab":h,"payload":"parts","amt":10.0});
        push(acts, {"kind":"ship","hab":h,"payload":"energy_cells","amt":15.0});
    }

    return acts;
}

fn space_apply_action(state, action) {
    if !state["space"]["unlocked"] { return state; }

    let fs = state["factions"];
    let sp = state["space"];

    if action["kind"] == "set_space_budget" {
        let f = fs[action["faction"]];
        # budget is a policy-like spend; cannot exceed credits/5
        let amt = action["amt"];
        if amt < 0.0 { amt = 0.0; }
        if amt > f["resources"]["credits"]/5.0 { amt = f["resources"]["credits"]/5.0; }
        sp["budget_monthly"] = amt;
        return state;
    }

    if action["kind"] == "build_hab" {
        let f = fs[action["faction"]];
        let hab = action["hab"];
        # costs
        let c = 300.0; let inf = 15.0; let metal = 80.0; let parts = 25.0;
        if hab == "Mars Dome" { c = 600.0; inf = 25.0; metal = 140.0; parts = 45.0; }
        if hab == "Lunar Vault" { c = 450.0; inf = 20.0; metal = 110.0; parts = 35.0; }

        if f["resources"]["credits"] >= c and f["resources"]["influence"] >= inf and f["resources"]["metal"] >= metal and f["resources"]["parts"] >= parts {
            f["resources"]["credits"] = f["resources"]["credits"] - c;
            f["resources"]["influence"] = f["resources"]["influence"] - inf;
            f["resources"]["metal"] = f["resources"]["metal"] - metal;
            f["resources"]["parts"] = f["resources"]["parts"] - parts;

            sp["habitats"][hab] = habitat_make(hab, f["name"]);
            emit_event("hab_built", {"hab":hab,"owner":f["name"]});
        }
        return state;
    }

    if action["kind"] == "ship" {
        let hab = action["hab"];
        if !has(sp["habitats"], hab) { return state; }
        let h = sp["habitats"][hab];
        let owner = fs[h["owner"]];

        let payload = action["payload"];
        let amt = action["amt"];

        # shipment costs (credits + metal + parts)
        let costC = 40.0 + 2.0*amt;
        let costM = 5.0 + 0.2*amt;
        let costP = 2.0 + 0.1*amt;

        if owner["resources"]["credits"] >= costC and owner["resources"]["metal"] >= costM and owner["resources"]["parts"] >= costP {
            owner["resources"]["credits"] = owner["resources"]["credits"] - costC;
            owner["resources"]["metal"] = owner["resources"]["metal"] - costM;
            owner["resources"]["parts"] = owner["resources"]["parts"] - costP;

            let eta = state["turn"] + travel_time(hab);
            push(sp["supply_queue"], shipment_make(hab, payload, amt, eta));
            emit_event("shipment", {"hab":hab,"payload":payload,"eta":eta});
        }
        return state;
    }

    return state;
}

fn apply_shipments(state) {
    let sp = state["space"];
    let q2 = [];
    for i in range(0, len(sp["supply_queue"])) {
        let sh = sp["supply_queue"][i];
        if sh["eta"] <= state["turn"] {
            let h = sp["habitats"][sh["hab"]];
            if sh["payload"] == "water" { h["water"] = h["water"] + sh["amt"]; }
            if sh["payload"] == "food" { h["o2"] = h["o2"] + sh["amt"] * 0.2; h["morale"] = h["morale"] + 1.0; }
            if sh["payload"] == "parts" { h["waste"] = clamp(h["waste"] - sh["amt"]*0.5, 0.0, 100.0); }
            if sh["payload"] == "energy_cells" { h["power_gen"] = h["power_gen"] + sh["amt"]*0.2; }
        } else {
            push(q2, sh);
        }
    }
    sp["supply_queue"] = q2;
    return state;
}

fn space_failure_roll(state, hab) {
    let sp = state["space"];
    let h = sp["habitats"][hab];
    let f = state["factions"][h["owner"]];

    let tau = abs(f["duology"]["o"] - f["duology"]["h"]);
    let rho = f["rho"];

    let base = 0.01 + (h["rad"]/1000.0) + 0.02*rho + 0.03*tau;
    let morale_factor = h["morale"]/200.0;

    if h["power_gen"] < h["power_use"] { base = base + 0.05; }
    if h["o2"] < 10.0 { base = base + 0.10; }
    if h["water"] < 10.0 { base = base + 0.08; }

    let p = clamp(base - morale_factor, 0.0, 0.60);
    if rng_float() < p {
        return true;
    }
    return false;
}

fn space_apply_failure(state, hab) {
    let sp = state["space"];
    let h = sp["habitats"][hab];

    # 6+ failure modes
    let modes = ["power_trip","scrubber_failure","micro_leak","waste_overflow","riot","hull_breach"];
    let mode = rng_choice(modes);

    if mode == "power_trip" {
        h["power_gen"] = clamp(h["power_gen"] - 20.0, 0.0, 9999.0);
        h["morale"] = clamp(h["morale"] - 5.0, 0.0, 100.0);
        return "Power trip on " + hab;
    }
    if mode == "scrubber_failure" {
        h["o2"] = clamp(h["o2"] - 15.0, 0.0, 9999.0);
        h["morale"] = clamp(h["morale"] - 7.0, 0.0, 100.0);
        return "O2 scrubber failure on " + hab;
    }
    if mode == "micro_leak" {
        h["water"] = clamp(h["water"] - 18.0, 0.0, 9999.0);
        return "Micro-leak drains water on " + hab;
    }
    if mode == "waste_overflow" {
        h["waste"] = clamp(h["waste"] + 25.0, 0.0, 100.0);
        h["morale"] = clamp(h["morale"] - 4.0, 0.0, 100.0);
        return "Waste overflow on " + hab;
    }
    if mode == "riot" {
        h["morale"] = clamp(h["morale"] - 20.0, 0.0, 100.0);
        return "Riot in " + hab;
    }
    # hull breach
    h["o2"] = clamp(h["o2"] - 40.0, 0.0, 9999.0);
    h["morale"] = clamp(h["morale"] - 15.0, 0.0, 100.0);
    return "Hull breach on " + hab;
}

fn space_collapse_check(state, hab) {
    let h = state["space"]["habitats"][hab];
    if h["o2"] <= 0.0 or h["water"] <= 0.0 or h["morale"] <= 0.0 or h["waste"] >= 100.0 {
        h["status"] = "collapsed";
        let rep = {
          "turn": state["turn"],
          "hab": h["name"],
          "owner": h["owner"],
          "vitals": {"o2":h["o2"],"water":h["water"],"waste":h["waste"],"rad":h["rad"],"morale":h["morale"],"power_gen":h["power_gen"],"power_use":h["power_use"]},
          "cause": "life_support_failure",
          "note": "Collapsed due to depleted essentials or unrest."
        };
        push(state["space"]["postmortems"], rep);
        emit_event("collapse", rep);
        return true;
    }
    return false;
}

fn space_tick(state) {
    state = space_unlock_if_ready(state);
    if !state["space"]["unlocked"] { return {"state": state, "lines": []}; }

    state = apply_shipments(state);

    let sp = state["space"];
    let habs = keys(sp["habitats"]);
    let lines = [];

    for i in range(0, len(habs)) {
        let hab = habs[i];
        let h = sp["habitats"][hab];
        if h["status"] == "collapsed" { continue; }

        # monthly consumption + degradation
        h["o2"] = h["o2"] - 8.0;
        h["water"] = h["water"] - 6.0;
        h["waste"] = clamp(h["waste"] + 6.0, 0.0, 100.0);

        # radiation drags morale
        h["morale"] = clamp(h["morale"] - (h["rad"]/200.0), 0.0, 100.0);

        # power deficit drains morale and increases waste
        if h["power_gen"] < h["power_use"] {
            h["morale"] = clamp(h["morale"] - 5.0, 0.0, 100.0);
            h["waste"] = clamp(h["waste"] + 5.0, 0.0, 100.0);
        }

        # failure roll
        if space_failure_roll(state, hab) {
            let msg = space_apply_failure(state, hab);
            push(lines, "SPACE: " + msg);
        }

        # collapse check
        if space_collapse_check(state, hab) {
            push(lines, "SPACE: " + hab + " COLLAPSED.");
        }
    }

    return {"state": state, "lines": lines};
}

fn ui_space(state, reveal) {
    let sp = state["space"];
    if !sp["unlocked"] { return "Space Ops: LOCKED (need orbital_fabrication)."; }
    let out = "Space Ops (Queue=" + str(len(sp["supply_queue"])) + ")\n";
    let habs = keys(sp["habitats"]);
    for i in range(0, len(habs)) {
        let h = sp["habitats"][habs[i]];
        out = out + "- " + h["name"] + " owner=" + h["owner"] + " status=" + h["status"] +
              " o2=" + str(h["o2"]) + " water=" + str(h["water"]) + " waste=" + str(h["waste"]) +
              " rad=" + str(h["rad"]) + " morale=" + str(h["morale"]) + "\n";
    }
    if reveal and len(sp["postmortems"]) > 0 {
        out = out + "Postmortems: " + str(len(sp["postmortems"])) + "\n";
    }
    return out;
}
