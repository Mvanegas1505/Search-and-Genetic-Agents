import random
import math
from collections import Counter, defaultdict

# ==========================
# Modelo del dominio
# ==========================

# Tipos de sesión y metadatos (intensity: 0 descanso/recuperación, 1 suave, 2 moderada, 3 intensa)
TYPE_INFO = {
    "REST":       {"intensity": 0, "group": None},
    "MOBILITY":   {"intensity": 0, "group": "mob"},
    "TECHNIQUE":  {"intensity": 1, "group": "tech"},
    "CARDIO":     {"intensity": 2, "group": "cardio"},
    "STR_UPPER":  {"intensity": 3, "group": "upper"},
    "STR_LOWER":  {"intensity": 3, "group": "lower"},
    "STR_FULL":   {"intensity": 3, "group": "full"},
}
ALL_TYPES = list(TYPE_INFO.keys())

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ==========================
# Parámetros del problema
# ==========================

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Duración del plan: 7 para semanal, o 28 para 4 semanas, etc.
WEEKS = 1          # cambia a 4 para plan mensual
DAYS = 7 * WEEKS

# Metas por semana (se escalan automáticamente si WEEKS>1)
WEEKLY_TARGET = {
    "STR_UPPER": 1,
    "STR_LOWER": 1,
    "STR_FULL":  0,
    "CARDIO":    2,
    "TECHNIQUE": 1,
    "MOBILITY":  1,
    "REST":      1,
}

# Restricciones de sobreentrenamiento / recuperación
MAX_CONSEC_INTENSE = 3                 # máximo de días intensos seguidos (CARDIO/STR_*)
MIN_REST_PER_WEEK  = 1                 # mínimo de días REST por semana
NO_CONSEC_SAME_STRENGTH_GROUP = True   # evita upper->upper o lower->lower en días consecutivos

# ==========================
# GA: hiperparámetros
# ==========================

POP_SIZE = 120
GENERATIONS = 300
ELITE_FRAC = 0.08
TOURNAMENT_K = 4
MUT_RATE_CHANGE = 0.20
MUT_RATE_SWAP = 0.10
EARLY_STOP_PATIENCE = 40   # generaciones sin mejora

# ==========================
# Utilidades
# ==========================

def scale_targets(weekly, weeks):
    scaled = {k: v * weeks for k, v in weekly.items()}
    # Ajuste suave: si la suma difiere de DAYS, rellena con MOBILITY/TECHNIQUE
    total = sum(scaled.values())
    if total < 7*weeks:
        scaled["MOBILITY"] = scaled.get("MOBILITY", 0) + (7*weeks - total)
    return scaled

TARGET = scale_targets(WEEKLY_TARGET, WEEKS)

def is_intense(day_type: str) -> bool:
    return TYPE_INFO[day_type]["intensity"] >= 2

def strength_group(day_type: str):
    return TYPE_INFO[day_type]["group"] if day_type.startswith("STR_") else None

# ==========================
# Representación y construcción
# ==========================

def make_random_plan() -> list:
    """
    Construye un plan aleatorio respetando aproximadamente los conteos objetivo.
    """
    bag = []
    for t, c in TARGET.items():
        bag += [t] * c
    # Si por redondeos sobra o falta, ajusta al tamaño DAYS
    while len(bag) < DAYS:
        bag.append(random.choice(ALL_TYPES))
    random.shuffle(bag)
    return bag[:DAYS]

# ==========================
# Evaluación (fitness)
# ==========================

def weekly_slices(plan):
    for w in range(WEEKS):
        yield plan[w*7:(w+1)*7]

def fitness(plan):
    """
    Mayor es mejor. Score base menos penalizaciones.
    También retornamos desglose para diagnóstico.
    """
    penalties = defaultdict(float)

    # 1) Conteos objetivo (equilibrio entre tipos)
    counts = Counter(plan)
    for t, target in TARGET.items():
        diff = abs(counts.get(t, 0) - target)
        penalties["counts_dev"] += 2.0 * (diff ** 1.5)  # penaliza no lineal

    # 2) Mínimo de descanso por semana
    for wk, week in enumerate(weekly_slices(plan), start=1):
        rest = week.count("REST")
        if rest < MIN_REST_PER_WEEK:
            penalties["min_rest"] += 6.0 * (MIN_REST_PER_WEEK - rest)

    # 3) Días intensos consecutivos y suavidad de la carga
    consec_intense = 0
    for i, day in enumerate(plan):
        if is_intense(day):
            consec_intense += 1
            # penaliza cada transición intensa-intensa para fomentar alternancia
            if i > 0 and is_intense(plan[i-1]):
                penalties["adjacent_intense"] += 0.8
        else:
            consec_intense = 0
        if consec_intense > MAX_CONSEC_INTENSE:
            penalties["max_consec_intense"] += 4.0 * (consec_intense - MAX_CONSEC_INTENSE)

    # 4) No repetir mismo grupo de fuerza dos días seguidos
    if NO_CONSEC_SAME_STRENGTH_GROUP:
        for a, b in zip(plan, plan[1:]):
            ga, gb = strength_group(a), strength_group(b)
            if ga and gb and ga == gb:
                penalties["same_strength_group_consec"] += 3.5

    # 5) Distribución uniforme de sesiones intensas por semana (varianza de gaps)
    for week in weekly_slices(plan):
        idx = [i for i, d in enumerate(week) if is_intense(d)]
        if len(idx) > 1:
            gaps = [b - a for a, b in zip(idx, idx[1:])]
            if gaps:
                var = (sum((g - (sum(gaps)/len(gaps)))**2 for g in gaps) / len(gaps))
                penalties["intense_spread_var"] += 0.6 * var

    # Score final
    base = 1000.0
    total_pen = sum(penalties.values())
    return base - total_pen, penalties

# ==========================
# Operadores GA
# ==========================

def tournament_selection(pop, k=TOURNAMENT_K):
    pick = random.sample(pop, k)
    pick.sort(key=lambda ind: ind["fitness"], reverse=True)
    return pick[0]["plan"]

def crossover_2pt(p1, p2):
    if len(p1) != len(p2):
        raise ValueError("Padres de distinto largo")
    if len(p1) < 3:
        return p1[:], p2[:]
    a, b = sorted(random.sample(range(1, len(p1)-1), 2))
    c1 = p1[:a] + p2[a:b] + p1[b:]
    c2 = p2[:a] + p1[a:b] + p2[b:]
    return c1, c2

def mutate(plan):
    plan = plan[:]  # copia
    # Mutación: cambio puntual
    if random.random() < MUT_RATE_CHANGE:
        i = random.randrange(len(plan))
        plan[i] = random.choice(ALL_TYPES)
    # Mutación: swap
    if random.random() < MUT_RATE_SWAP:
        i, j = random.sample(range(len(plan)), 2)
        plan[i], plan[j] = plan[j], plan[i]
    return plan

# ==========================
# Bucle evolutivo
# ==========================

def evolve():
    # Población inicial
    population = []
    for _ in range(POP_SIZE):
        plan = make_random_plan()
        score, _ = fitness(plan)
        population.append({"plan": plan, "fitness": score})

    elite_k = max(1, int(ELITE_FRAC * POP_SIZE))
    best_ever = max(population, key=lambda ind: ind["fitness"])
    best_no_improve = 0

    for gen in range(1, GENERATIONS + 1):
        # Elitismo
        population.sort(key=lambda ind: ind["fitness"], reverse=True)
        new_pop = population[:elite_k]

        # Reproducción
        while len(new_pop) < POP_SIZE:
            p1 = tournament_selection(population)
            p2 = tournament_selection(population)
            c1, c2 = crossover_2pt(p1, p2)
            c1 = mutate(c1)
            c2 = mutate(c2)
            s1, _ = fitness(c1)
            s2, _ = fitness(c2)
            new_pop.append({"plan": c1, "fitness": s1})
            if len(new_pop) < POP_SIZE:
                new_pop.append({"plan": c2, "fitness": s2})

        population = new_pop

        # Tracking mejor individuo
        current_best = max(population, key=lambda ind: ind["fitness"])
        if current_best["fitness"] > best_ever["fitness"]:
            best_ever = current_best
            best_no_improve = 0
        else:
            best_no_improve += 1

        # Parada temprana
        if best_no_improve >= EARLY_STOP_PATIENCE:
            # print(f"Early stop at generation {gen}")
            break

    # Recalcula desglose de penales del mejor
    best_score, breakdown = fitness(best_ever["plan"])
    best_ever["fitness"] = best_score
    best_ever["breakdown"] = breakdown
    return best_ever

# ==========================
# Presentación
# ==========================

def plan_counts(plan):
    c = Counter(plan)
    return {t: c.get(t, 0) for t in ALL_TYPES}

def pretty_plan(plan):
    out = []
    for w, week in enumerate(weekly_slices(plan), start=1):
        out.append(f"Week {w}:")
        for i, d in enumerate(week):
            out.append(f"  {DAY_NAMES[i]}: {d}")
    return "\n".join(out)

def print_summary(best):
    print("\n=== BEST PLAN ===")
    print(f"Fitness: {best['fitness']:.2f}")
    print(pretty_plan(best["plan"]))
    print("\nCounts (total):")
    counts = plan_counts(best["plan"])
    for t in ALL_TYPES:
        tgt = TARGET.get(t, 0)
        print(f"  {t:<11} {counts[t]:>2}  (target {tgt})")
    print("\nPenalty breakdown (lower is better):")
    for k, v in sorted(best["breakdown"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:<28} {v:.2f}")

if __name__ == "__main__":
    best = evolve()
    print_summary(best)

    # Nota rápida:
    # - Cambia WEEKS=4 para un plan mensual.
    # - Ajusta WEEKLY_TARGET, MAX_CONSEC_INTENSE y MIN_REST_PER_WEEK según tu deporte/objetivo.
    # - Incrementa POP_SIZE/GENERATIONS para más calidad (más costo computacional).
