from ref import *
def poly_rows(pts, closed=True, rot=0.0, shift=(0, 0), scale=1.0):
    pts = np.asarray(pts, float)
    c, s = math.cos(rot), math.sin(rot)
    R = np.array([[c, -s], [s, c]])
    pts = (pts @ R.T + np.asarray(shift))*scale
    if closed: pts = np.vstack([pts, pts[:1]])
    return '\n'.join(f'{pts[i,0]:.17g} {pts[i,1]:.17g} {pts[i+1,0]:.17g} {pts[i+1,1]:.17g}' for i in range(len(pts)-1))
def rect(a, b, x0=0.0, y0=0.0):  # clockwise
    return [(x0-a, y0-b), (x0-a, y0+b), (x0+a, y0+b), (x0+a, y0-b)]
def make(name, N=0, **tr):
    P = lambda pts, closed=True: poly_rows(pts, closed, **tr)
    if name == 'pec':
        return geo([(2, f'2 {N} 0 0 0', P(rect(.09, .04)))])
    if name == 'ibc':
        return geo([(2, f'2 {N} 7 0 0', P(rect(.09, .04)))], ibc='7 constant 150 60 0 0')
    if name == 'pecibc':   # top face PEC, rest IBC, stitched
        r = rect(.09, .04)
        return geo([(2, f'2 {N} 0 0 0', P([r[1], r[2]], False)), (2, f'2 {N} 7 0 0', P([r[2], r[3], r[0], r[1]], False))], ibc='7 constant 150 60 0 0')
    if name == 'diel':
        return geo([(3, f'3 {N} 0 1 0', P(rect(.09, .04)))], diel='1 3.0 -0.1 1.2 -0.05')
    if name == 'diel_ll':
        return geo([(3, f'3 {N} 0 1 0', P(rect(.09, .04)))], diel='1 3.0 0 1.0 0')
    if name == 'coat':
        return geo([(3, f'3 {N} 0 1 0', P(rect(.09, .04))), (4, f'4 {N} 0 1 0', P(rect(.06, .02, 0.01, 0.005)))], diel='1 3.0 -0.1 1.2 -0.05')
    if name == 'coatibc':
        return geo([(3, f'3 {N} 0 1 0', P(rect(.09, .04))), (4, f'4 {N} 7 1 0', P(rect(.06, .02, 0.01, 0.005)))], diel='1 3.0 -0.1 1.2 -0.05', ibc='7 constant 150 60 0 0')
    if name == 'two':
        return geo([(3, f'3 {N} 0 1 0', P(rect(.09, .04))), (5, f'5 {N} 0 1 2', P(rect(.06, .02, 0.01, 0.005)))], diel='1 3.0 -0.1 1.2 -0.05\n2 5 -0.3 1 0')
    if name == 'sheet':
        return geo([(1, f'1 {N} 7 0 0', P([(-.08, -.01), (0.0, 0.02), (.09, 0.0)], False))], ibc='7 constant 150 60 0 0')
    if name == 'sheetpec':
        return geo([(1, f'1 {N} 7 0 0', P([(-.08, .09), (.09, 0.08)], False)), (2, f'2 {N} 0 0 0', P(rect(.09, .04)))], ibc='7 constant 150 60 0 0')
    if name == 'thin':
        return geo([(1, f'1 {N} 7 0 0', P([(-.08, -.01), (.09, 0.0)], False))], ibc='7 thin_dielectric 0.0005 2', diel='2 3.0 -0.02 1.0 0.0')
    if name == 'strip':
        return geo([(2, f'2 {N} 0 0 0', P([(-.08, -.01), (.09, 0.0)], False))])
    if name == 'twobody':
        return geo([(2, f'2 {N} 0 0 0', P(rect(.05, .03, -.08, 0))), (3, f'3 {N} 0 1 0', P(rect(.04, .03, .07, 0.02)))], diel='1 3.0 -0.1 1.2 -0.05')
    raise KeyError(name)
ALL = ['pec', 'ibc', 'pecibc', 'diel', 'coat', 'coatibc', 'two', 'sheet', 'sheetpec', 'thin', 'twobody']
