import "rules/war.zs";
import "rules/diplomacy.zs";

fn event_weight(state, name) {
    let t = state["turn"];

    if name == "solar_flare" { return 4.0; }
    if name == "silicon_glut" { return 3.0; }
    if name == "labor_strike" { return 3.0; }
    if name == "border_incident" { return 2.5; }
    if name == "spy_scandal" { return 2.0; }
    if name == "pirate_raiders" { return 2.0; }
    if name == "reactor_breakthrough" { return 1.5; }
    if name == "food_blight" { return 3.0; }
    if name == "peace_summit" { return 2.0; }
    if name == "inflation_panic" { return 2.0 + 4.0*state["market"]["inflation"]; }
    if name == "coup_whispers" { return 1.0; }

    return 0.0;
}

fn pick_event(state) {
    let names = ["solar_flare","silicon_glut","labor_strike","border_incident","spy_scandal","pirate_raiders","reactor_breakthrough","food_blight","peace_summit","inflation_panic","coup_whispers"];
    let total = 0.0;
    for i in range(0, len(names)) { total = total + event_weight(state, names[i]); }
    let r = rng_float() * total;
    let acc = 0.0;
    for i in range(0, len(names)) {
        acc = acc + event_weight(state, names[i]);
        if r <= acc { return names[i]; }
    }
    return names[0];
}

fn apply_event(state, ev) {
    let fs = state["factions"];
    let names = keys(fs);

    if ev == "solar_flare" {
        let who = rng_choice(names);
        fs[who]["resources"]["energy"] = clamp(fs[who]["resources"]["energy"] - 40.0, 0.0, 99999.0);
        fs[who]["resources"]["morale"] = clamp(fs[who]["resources"]["morale"] - 3.0, 0.0, 100.0);
        return ["Solar flare disrupts grids in " + who + "."];
    }

    if ev == "silicon_glut" {
        let who = rng_choice(names);
        fs[who]["resources"]["silicon"] = fs[who]["resources"]["silicon"] + 30.0;
        fs[who]["resources"]["credits"] = fs[who]["resources"]["credits"] + 40.0;
        return ["Silicon glut boosts " + who + " exports."];
    }

    if ev == "labor_strike" {
        let who = rng_choice(names);
        fs[who]["unrest"] = clamp(fs[who]["unrest"] + 8.0, 0.0, 100.0);
        fs[who]["resources"]["credits"] = clamp(fs[who]["resources"]["credits"] - 30.0, 0.0, 99999.0);
        return ["Labor strike in " + who + " increases unrest."];
    }

    if ev == "border_incident" {
        let a = rng_choice(names);
        let b = rng_choice(names);
        if a == b { b = names[0]; }
        # if already at war, skip
        if is_at_war(state, a) or is_at_war(state, b) { return ["Border incident fizzles; tensions already peaked."]; }
        push(state["wars"], war_make(a,b));
        return ["Border incident ignites war between " + a + " and " + b + "!"];
    }

    if ev == "spy_scandal" {
        let who = rng_choice(names);
        fs[who]["rho"] = fs[who]["rho"] + 0.10;
        fs[who]["intel"] = clamp(fs[who]["intel"] + 8.0, 0.0, 100.0);
        return ["Spy scandal shakes " + who + ". Paranoia rises."];
    }

    if ev == "pirate_raiders" {
        let who = rng_choice(names);
        fs[who]["resources"]["metal"] = clamp(fs[who]["resources"]["metal"] - 15.0, 0.0, 99999.0);
        fs[who]["resources"]["credits"] = clamp(fs[who]["resources"]["credits"] - 20.0, 0.0, 99999.0);
        return ["Pirate raiders hit " + who + "'s convoys."];
    }

    if ev == "reactor_breakthrough" {
        let who = rng_choice(names);
        fs[who]["tech"]["fusion_basics"] = 1;
        fs[who]["resources"]["energy"] = fs[who]["resources"]["energy"] + 60.0;
        return ["Reactor breakthrough! " + who + " unlocks fusion basics."];
    }

    if ev == "food_blight" {
        let who = rng_choice(names);
        fs[who]["resources"]["food"] = clamp(fs[who]["resources"]["food"] - 50.0, 0.0, 99999.0);
        fs[who]["unrest"] = clamp(fs[who]["unrest"] + 6.0, 0.0, 100.0);
        return ["Food blight hits " + who + ". Rations tighten."];
    }

    if ev == "peace_summit" {
        if len(state["wars"]) == 0 { return ["Peace summit held. No active wars to resolve."]; }
        # end first war with treaty
        let w = state["wars"][0];
        state["wars"] = [];
        push(state["treaties"], treaty_make("non_aggression", w["a"], w["b"], 12));
        return ["Peace summit ends the war. Non-aggression pact signed."];
    }

    if ev == "inflation_panic" {
        state["market"]["inflation"] = clamp(state["market"]["inflation"] + 0.05, 0.0, 0.50);
        return ["Inflation panic spreads. Prices surge."];
    }

    if ev == "coup_whispers" {
        let who = rng_choice(names);
        # hidden: high rho increases coup impact
        let hit = 2.0 + 10.0 * clamp(fs[who]["rho"], 0.0, 2.0);
        fs[who]["unrest"] = clamp(fs[who]["unrest"] + hit, 0.0, 100.0);
        return ["Coup whispers in " + who + ". Unrest ticks upward."];
    }

    return ["Nothing happens."];
}

fn events_tick(state) {
    # one event per tick with 70% chance
    if rng_float() < 0.70 {
        let ev = pick_event(state);
        let lines = apply_event(state, ev);
        return {"state": state, "lines": lines};
    }
    return {"state": state, "lines": ["Quiet month."]};
}
