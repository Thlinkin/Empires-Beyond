fn make_faction(name, traits, pop, duoo, duoh) {
    let f = {};
    f["name"] = name;
    f["traits"] = traits;
    f["pop"] = pop;
    f["unrest"] = 5.0;
    f["war_exhaust"] = 0.0;
    f["intel"] = 10.0;

    f["resources"] = {
        "food": 200.0, "water": 200.0, "energy": 200.0,
        "metal": 120.0, "silicon": 80.0,
        "credits": 500.0, "influence": 50.0, "morale": 60.0,
        "units": 30.0, "parts": 20.0
    };

    f["prod"] = {
        "food": 40.0, "water": 35.0, "energy": 30.0,
        "metal": 15.0, "silicon": 10.0,
        "credits": 60.0, "influence": 4.0, "morale": 0.0,
        "units": 0.0, "parts": 1.0
    };

    f["policies"] = {};
    f["tech"] = {};
    f["duology"] = {"o": duoo, "h": duoh};
    f["rho"] = 0.0;
    return f;
}

fn init_factions() {
    let fs = {};
    fs["Gilded Fleet"] = make_faction("Gilded Fleet", ["trader","cosmopolitan"], 1200, 0.55, 0.60);
    fs["Iron Choir"]  = make_faction("Iron Choir", ["militarist","disciplined"], 900, 0.80, 0.35);
    fs["Verdant Union"]= make_faction("Verdant Union", ["agrarian","resilient"], 1100, 0.60, 0.45);
    fs["Lunar Syndics"]= make_faction("Lunar Syndics", ["techno","covert"], 700, 0.50, 0.70);

    return fs;
}
