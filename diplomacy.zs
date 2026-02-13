import "rules/math_system.zs";

fn treaty_make(kind, a, b, turns) {
    return {"kind":kind, "a":a, "b":b, "ttl":turns};
}

fn treaty_bonus(kind) {
    if kind == "trade_pact" { return 8.0; }
    if kind == "non_aggression" { return 10.0; }
    if kind == "research_exchange" { return 6.0; }
    if kind == "alliance" { return 14.0; }
    return 0.0;
}

fn treaty_lambda(kind) {
    if kind == "trade_pact" { return 0.08; }
    if kind == "non_aggression" { return 0.10; }
    if kind == "research_exchange" { return 0.06; }
    if kind == "alliance" { return 0.12; }
    return 0.0;
}

fn trust_score(state, a, b) {
    let fa = state["factions"][a];
    let fb = state["factions"][b];
    let ell = tmdc_alignment(fa["duology"], fb["duology"]);

    let tb = 0.0;
    let ts = state["treaties"];
    for i in range(0, len(ts)) {
        let t = ts[i];
        if (t["a"] == a and t["b"] == b) or (t["a"] == b and t["b"] == a) {
            tb = tb + treaty_bonus(t["kind"]) * (1.0 / (1.0 + (5.0*count)));
            count = count + 1.0;
        }
    }

    let base = 50.0 + 30.0 * ell - 15.0 * fa["rho"] - 15.0 * fb["rho"] + tb;
    return clamp(base, 0.0, 100.0);
}

fn trust_band(score) {
    if score >= 80.0 { return "Allied"; }
    if score >= 60.0 { return "Warm"; }
    if score >= 40.0 { return "Neutral"; }
    if score >= 20.0 { return "Cold"; }
    return "Hostile";
}

fn diplomacy_tick(state) {
    let fs = state["factions"];
    let names = keys(fs);

    # decrement treaties
    let out = [];
    for i in range(0, len(state["treaties"])) {
        let t = state["treaties"][i];
        t["ttl"] = t["ttl"] - 1;
        if t["ttl"] > 0 { push(out, t); }
    }
    state["treaties"] = out;

    # apply tertiation to each faction (peace heals, war hurts later in war.zs)
    for i in range(0, len(names)) {
        let f = fs[names[i]];
        let lam = 0.06; # base adaptability

        # treaties raise lambda slightly
        for j in range(0, len(state["treaties"])) {
            let t2 = state["treaties"][j];
            if t2["a"] == f["name"] or t2["b"] == f["name"] {
                lam = lam + treaty_lambda(t2["kind"]);
            }
        }

        # propaganda masks unrest (hidden)
        if has(f["policies"], "propaganda_ministry") and f["policies"]["propaganda_ministry"] {
            lam = lam + 0.03;
        }

        let duo2 = tmdc_tertiate(f["duology"]["o"], f["duology"]["h"], clamp(lam,0.0,0.35));
        f["duology"] = duo2;

        # update resonance debt
        f["rho"] = tmdc_update_debt(f["rho"], f["duology"]["o"], f["duology"]["h"], 0.20);
    }

    return state;
}
