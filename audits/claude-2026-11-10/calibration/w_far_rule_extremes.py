"""Extension of w_far_rule.py to sliver panels and very low frequency."""
import w_far_rule as W

W.RATIO = (1e-4, 1e-5, 1e-6)
W.KL = (1e-8, 1e-6, 1e-4, 0.15, 0.5, 1.0, 1.5, 3.0)
W.SEPARATION = (3.0, 5.0, 10.0)
worst = W.run(samples=8, seed=1)
print("{} cells measured, {} dropped".format(worst.get("measured", 0), worst.get("dropped", 0)))
print("slivers (length ratio 1e-4 .. 1e-6) and |k|L down to 1e-8; columns order " + str(W.ORDERS))
for separation in W.SEPARATION:
    print("separation {:g} panel lengths".format(separation))
    for kl in W.KL:
        print("  |k|L {:<7g} ".format(kl) + "  ".join("{:.1e}".format(worst[separation, kl, q]) for q in W.ORDERS))
W.RATIO = (1.0, 0.1, 0.001)
W.KL = (1e-8, 1e-6)
worst = W.run(samples=8, seed=2)
print("{} cells measured, {} dropped".format(worst.get("measured", 0), worst.get("dropped", 0)))
print("ordinary length ratios at |k|L 1e-8 and 1e-6")
for separation in W.SEPARATION:
    for kl in W.KL:
        print("  separation {:<3g} |k|L {:<7g} ".format(separation, kl) + "  ".join("{:.1e}".format(worst[separation, kl, q]) for q in W.ORDERS))
