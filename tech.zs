fn tech_list() {
    return [
      "fusion_basics",
      "orbital_fabrication",
      "hydroponics",
      "signal_intelligence",
      "railguns",
      "radiation_medicine"
    ];
}

fn init_tech(faction) {
    let ts = tech_list();
    for i in range(0, len(ts)) {
        faction["tech"][ts[i]] = 0;
    }
}

fn tech_cost(name) {
    if name == "fusion_basics" { return {"credits": 250.0, "influence": 10.0}; }
    if name == "orbital_fabrication" { return {"credits": 350.0, "influence": 15.0}; }
    if name == "hydroponics" { return {"credits": 200.0, "influence": 8.0}; }
    if name == "signal_intelligence" { return {"credits": 220.0, "influence": 12.0}; }
    if name == "railguns" { return {"credits": 300.0, "influence": 12.0}; }
    if name == "radiation_medicine" { return {"credits": 280.0, "influence": 10.0}; }
    return {"credits": 9999.0, "influence": 9999.0};
}

fn tech_prereq(name) {
    if name == "orbital_fabrication" { return "fusion_basics"; }
    if name == "railguns" { return "signal_intelligence"; }
    if name == "radiation_medicine" { return "fusion_basics"; }
    return null;
}
