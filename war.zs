import "rules/math_system.zs";

fn war_make(a,b) {
    return {"a":a,"b":b,"months":0,"a_losses":0.0,"b_losses":0.0};
}

fn is_at_war(state, name) {
    for i in range(0, len(state["wars"])) {
        let w = state["wars"][i];
        if w["a"] == name or w["b"] == name { return true; }
    }
    return false;
}

fn war_tick(state) {
    let fs = state["factions"];

    for i in range(0, len(state["wars"])) {
        let w = state["wars"][i];
        w["months"] = w["months"] + 1;

        let A = fs[w["a"]];
        let B = fs[w["b"]];

        # war lowers tertiation (hidden) by boosting tension persistence:
        # we simulate by adding small debt and reducing morale.
        A["rho"] = A["rho"] + 0.03;
        B["rho"] = B["rho"] + 0.03;

        # supply derived from food + energy
        let supA = (A["resources"]["food"] + A["resources"]["energy"]) / 100.0;
        let supB = (B["resources"]["food"] + B["resources"]["energy"]) / 100.0;

        let powA = A["resources"]["units"] * (0.6 + 0.004 * A["resources"]["morale"]) * (1.0 + 0.1 * supA);
        let powB = B["resources"]["units"] * (0.6 + 0.004 * B["resources"]["morale"]) * (1.0 + 0.1 * supB);

        # penalties from resonance debt
        powA = powA * (1.0 - 0.15 * clamp(A["rho"],0.0,2.0));
        powB = powB * (1.0 - 0.15 * clamp(B["rho"],0.0,2.0));

        # casualties scale
        let casA = clamp(0.5 + 0.02 * powB, 0.0, 10.0);
        let casB = clamp(0.5 + 0.02 * powA, 0.0, 10.0);

        A["resources"]["units"] = clamp(A["resources"]["units"] - casA, 0.0, 9999.0);
        B["resources"]["units"] = clamp(B["resources"]["units"] - casB, 0.0, 9999.0);

        w["a_losses"] = w["a_losses"] + casA;
        w["b_losses"] = w["b_losses"] + casB;

        A["war_exhaust"] = clamp(A["war_exhaust"] + 2.0 + 2.0*A["rho"], 0.0, 100.0);
        B["war_exhaust"] = clamp(B["war_exhaust"] + 2.0 + 2.0*B["rho"], 0.0, 100.0);

        A["resources"]["morale"] = clamp(A["resources"]["morale"] - 1.0, 0.0, 100.0);
        B["resources"]["morale"] = clamp(B["resources"]["morale"] - 1.0, 0.0, 100.0);

        # end condition: if one side units too low or exhaustion too high, war ends (peace enforced)
        if A["resources"]["units"] < 5.0 or A["war_exhaust"] > 95.0 {
            emit_event("peace", {"winner": B["name"], "loser": A["name"]});
            w["months"] = 999999; # mark
        }
        if B["resources"]["units"] < 5.0 or B["war_exhaust"] > 95.0 {
            emit_event("peace", {"winner": A["name"], "loser": B["name"]});
            w["months"] = 999999;
        }
    }

    # remove ended wars
    let nw = [];
    for i in range(0, len(state["wars"])) {
        let w = state["wars"][i];
        if w["months"] < 999999 { push(nw, w); }
    }
    state["wars"] = nw;

    return state;
}
