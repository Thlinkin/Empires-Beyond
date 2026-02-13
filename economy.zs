fn apply_policy_econ_mods(faction) {
    # base multipliers
    let mult = {"food":1.0,"water":1.0,"energy":1.0,"metal":1.0,"silicon":1.0,"credits":1.0,"influence":1.0,"parts":1.0};

    if has(faction["policies"], "free_market") and faction["policies"]["free_market"] {
        mult["credits"] = mult["credits"] + 0.15;
        mult["metal"] = mult["metal"] + 0.05;
        mult["silicon"] = mult["silicon"] + 0.05;
    }
    if has(faction["policies"], "price_controls") and faction["policies"]["price_controls"] {
        mult["credits"] = mult["credits"] - 0.10;
        mult["food"] = mult["food"] - 0.05;
        mult["morale"] = 1.0; # handled elsewhere (morale bump)
    }
    if has(faction["policies"], "green_reactors") and faction["policies"]["green_reactors"] {
        mult["energy"] = mult["energy"] + 0.20;
    }
    if has(faction["policies"], "research_grants") and faction["policies"]["research_grants"] {
        mult["silicon"] = mult["silicon"] + 0.10;
        mult["credits"] = mult["credits"] - 0.05;
    }
    if has(faction["policies"], "space_priority") and faction["policies"]["space_priority"] {
        mult["parts"] = mult["parts"] + 0.20;
        mult["metal"] = mult["metal"] - 0.05; # opportunity cost
    }
    return mult;
}

fn consume_basics(faction) {
    # per 1000 pop monthly
    let p = faction["pop"] / 1000.0;
    faction["resources"]["food"] = faction["resources"]["food"] - 30.0 * p;
    faction["resources"]["water"] = faction["resources"]["water"] - 25.0 * p;
    faction["resources"]["energy"] = faction["resources"]["energy"] - 18.0 * p;
}

fn produce(faction) {
    let mult = apply_policy_econ_mods(faction);
    let ks = keys(faction["prod"]);
    for i in range(0, len(ks)) {
        let r = ks[i];
        let base = faction["prod"][r];
        let m = 1.0;
        if has(mult, r) { m = mult[r]; }
        faction["resources"][r] = faction["resources"][r] + base * m;
    }
}

fn clamp_no_neg(faction) {
    let ks = keys(faction["resources"]);
    for i in range(0, len(ks)) {
        let r = ks[i];
        if faction["resources"][r] < 0.0 { faction["resources"][r] = 0.0; }
    }
}

fn econ_tick(state) {
    let fs = state["factions"];
    let names = keys(fs);

    # production + consumption
    for i in range(0, len(names)) {
        let f = fs[names[i]];
        produce(f);
        consume_basics(f);

        # morale feedback
        if f["resources"]["food"] < 20.0 or f["resources"]["water"] < 20.0 {
            f["resources"]["morale"] = f["resources"]["morale"] - 5.0;
            f["unrest"] = f["unrest"] + 4.0;
        } else {
            f["resources"]["morale"] = f["resources"]["morale"] + 0.5;
        }

        # price controls short-term morale bump, long-term supply drag via prod mods
        if has(f["policies"], "price_controls") and f["policies"]["price_controls"] {
            f["resources"]["morale"] = f["resources"]["morale"] + 1.0;
        }

        # cap morale/unrest
        f["resources"]["morale"] = clamp(f["resources"]["morale"], 0.0, 100.0);
        f["unrest"] = clamp(f["unrest"], 0.0, 100.0);

        clamp_no_neg(f);
    }

    # macro inflation
    let mkt = state["market"];
    let printed = mkt["credit_supply_growth"];
    let metal_backed = mkt["metal_backing"];

    let base = 0.01 * printed - 0.005 * metal_backed;

    # hidden interaction: debt amplifies inflation
    let rho_avg = 0.0;
    for j in range(0, len(names)) { rho_avg = rho_avg + fs[names[j]]["rho"]; }
    rho_avg = rho_avg / (len(names) * 1.0);

    let growth = base * (1.0 + 0.25 * rho_avg);
    mkt["inflation"] = clamp(mkt["inflation"] + growth, 0.0, 0.50);

    return state;
}
