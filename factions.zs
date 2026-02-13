# ==========================
# TMDC: Tertiated Monosyllabic Duology Calculus
# ==========================

fn clamp(x, lo, hi) {
    if x < lo { return lo; }
    if x > hi { return hi; }
    return x;
}

fn abs(x) {
    if x < 0 { return -x; }
    return x;
}

# duology object is represented as a map:
# { "o": float, "h": float }

fn duo_make(o, h) {
    let d = {};
    d["o"] = clamp(o, 0.0, 1.0);
    d["h"] = clamp(h, 0.0, 1.0);
    return d;
}

fn tmdc_phase(o, h) {
    return (o + h) / 2.0;
}

fn tmdc_tension(o, h) {
    return abs(o - h);
}

fn tmdc_tertiate(o, h, lambda) {
    let lam = clamp(lambda, 0.0, 1.0);

    let o2 = o + lam * (h - o) * (1.0 - o);
    let h2 = h + lam * (o - h) * (1.0 - h);

    return duo_make(o2, h2);
}

fn tmdc_merge(duoA, duoB, alpha) {
    let a = clamp(alpha, 0.0, 1.0);

    let o = (1.0 - a) * duoA["o"] + a * duoB["o"];
    let h = (1.0 - a) * duoA["h"] + a * duoB["h"];

    return duo_make(o, h);
}

# returns in [-1,1]
fn tmdc_alignment(duoA, duoB) {
    let dO = abs(duoA["o"] - duoB["o"]);
    let dH = abs(duoA["h"] - duoB["h"]);

    let L = 1.0 - (dO + dH);
    L = clamp(L, 0.0, 1.0);

    let ell = 2.0 * L - 1.0;
    return ell;
}

fn tmdc_update_debt(rho, o, h, mu) {
    let phase = tmdc_phase(o, h);
    let tension = tmdc_tension(o, h);

    let r2 = rho + tension * tension - mu * phase;
    if r2 < 0.0 { r2 = 0.0; }
    return r2;
}
