"""Moved BoR definitions: identical ASTs, and every global name a moved function reads
resolves to the very same object the solver module sees."""
import ast, sys, types, importlib, inspect, dis
base, new = sys.argv[1], sys.argv[2]
def defs(path):
    src = open(path, encoding='utf-8').read(); tree = ast.parse(src)
    return {n.name: ast.dump(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}, tree
b_defs, b_tree = defs(base + '/tools/GHOST/ghost_backend/bor/solver.py')
n_defs, n_tree = defs(new + '/tools/GHOST/ghost_backend/bor/solver.py')
moved = {}
for mod in ('constraints', 'storage', 'validation'):
    d, _ = defs(new + '/tools/GHOST/ghost_backend/bor/%s.py' % mod)
    for k, v in d.items(): moved[k] = (mod, v)
removed = sorted(set(b_defs) - set(n_defs)); added = sorted(set(n_defs) - set(b_defs))
print('top-level defs in solver: base', len(b_defs), 'new', len(n_defs), '| removed', len(removed), '| added', added)
print('removed defs not found in a new module:', [r for r in removed if r not in moved])
print('moved defs with different AST:', [r for r in removed if r in moved and moved[r][1] != b_defs[r]])
print('remaining defs with different AST:', [k for k in n_defs if k in b_defs and n_defs[k] != b_defs[k]])
# module-level statements other than defs/imports that changed (constants, caches)
def others(tree): return [ast.dump(n) for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))]
bo, no = others(b_tree), others(n_tree)
print('module-level non-def statements: base', len(bo), 'new', len(no), '| dropped from solver:', len([x for x in bo if x not in no]), '| new in solver:', len([x for x in no if x not in bo]))
sys.path.insert(0, new + '/tools/GHOST')
S = importlib.import_module('ghost_backend.bor.solver')
bad = []; checked = 0; names_checked = 0
for name in removed:
    mod = importlib.import_module('ghost_backend.bor.' + moved[name][0])
    obj = getattr(mod, name)
    if getattr(S, name, None) is not obj: bad.append(('not re-exported identically', name))
    funcs = [obj] if inspect.isfunction(obj) else [v for v in vars(obj).values() if inspect.isfunction(v)] + [v.fget for v in vars(obj).values() if isinstance(v, property)]
    for f in funcs:
        codes = [f.__code__]
        while codes:
            c = codes.pop(); codes += [k for k in c.co_consts if isinstance(k, types.CodeType)]
            for ins in dis.get_instructions(c):
                if ins.opname in ('LOAD_GLOBAL', 'LOAD_NAME'):
                    g = ins.argval; names_checked += 1
                    if g in f.__globals__:
                        if hasattr(S, g) and getattr(S, g) is not f.__globals__[g] and g not in dir(__builtins__): bad.append(('different object than solver sees', name, g))
                    elif not hasattr(__builtins__, g): bad.append(('unresolved global', name, g))
    checked += 1
print('moved definitions checked', checked, '| global-name reads checked', names_checked, '| problems', bad)
# constants moved to storage: values equal to base solver's
import importlib.util
spec = importlib.util.spec_from_file_location('base_solver_src', base + '/tools/GHOST/ghost_backend/bor/solver.py')
base_consts = {t.id: ast.literal_eval(n.value) for n in b_tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name) and isinstance(n.value, (ast.Constant, ast.UnaryOp, ast.BinOp)) and all(isinstance(x, (ast.Constant, ast.UnaryOp, ast.BinOp, ast.operator, ast.unaryop)) for x in ast.walk(n.value))} if False else {}
vals = {}
for n in b_tree.body:
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
        try: vals[n.targets[0].id] = eval(compile(ast.Expression(n.value), 'x', 'eval'), {})
        except Exception: pass
diff = [(k, v, getattr(S, k, 'MISSING')) for k, v in vals.items() if not hasattr(S, k) or getattr(S, k) != v]
print('base solver literal constants', len(vals), '| missing or changed in new solver namespace:', diff)
