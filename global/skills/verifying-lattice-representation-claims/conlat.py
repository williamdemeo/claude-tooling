"""Congruence lattice of a finite unary algebra read from a UACalc .ua file."""
import sys, itertools
import xml.etree.ElementTree as ET


def read_algebras(path):
    root = ET.parse(path).getroot()
    out = {}
    for a in root.findall('.//basicAlgebra'):
        name = (a.findtext('algName') or '?').strip()
        card = int((a.findtext('cardinality') or '0').strip())
        ops = []
        for op in a.findall('.//op'):
            ar = int((op.findtext('.//arity') or '0').strip())
            if ar != 1:
                continue
            vals = []
            for r in op.findall('.//row'):
                vals += [int(x) for x in r.text.replace(',', ' ').split()]
            ops.append(tuple(vals))
        out[name] = (card, ops)
    return out


def normalize(part, n):
    """Canonical form: tuple of block-representatives."""
    rep = list(range(n))

    def find(x):
        while rep[x] != x:
            rep[x] = rep[rep[x]]
            x = rep[x]
        return x

    for a, b in part:
        ra, rb = find(a), find(b)
        if ra != rb:
            rep[max(ra, rb)] = min(ra, rb)
    return tuple(find(i) for i in range(n))


def close(pairs, n, ops):
    """Smallest congruence containing `pairs`."""
    rep = list(range(n))

    def find(x):
        while rep[x] != x:
            rep[x] = rep[rep[x]]
            x = rep[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        rep[max(ra, rb)] = min(ra, rb)
        return True

    for a, b in pairs:
        union(a, b)
    changed = True
    while changed:
        changed = False
        for f in ops:
            for x in range(n):
                for y in range(x + 1, n):
                    if find(x) == find(y) and union(f[x], f[y]):
                        changed = True
    return tuple(find(i) for i in range(n))


def join(p, q, n, ops):
    pairs = [(i, p[i]) for i in range(n)] + [(i, q[i]) for i in range(n)]
    return close(pairs, n, ops)


def leq(p, q, n):
    """p <= q iff every p-block sits inside a q-block."""
    return all(q[i] == q[p[i]] for i in range(n))


def con(n, ops):
    principals = {close([(a, b)], n, ops) for a in range(n) for b in range(a + 1, n)}
    univ = {tuple(range(n))} | principals
    frontier = set(univ)
    while frontier:
        new = set()
        for p in frontier:
            for q in principals:
                j = join(p, q, n, ops)
                if j not in univ:
                    new.add(j)
        univ |= new
        frontier = new
    return sorted(univ)


def covers(univ, n):
    idx = {p: i for i, p in enumerate(univ)}
    cov = []
    for p in univ:
        for q in univ:
            if p != q and leq(p, q, n):
                if not any(r not in (p, q) and leq(p, r, n) and leq(r, q, n) for r in univ):
                    cov.append((idx[p], idx[q]))
    return cov


def iso_to(cov_a, na, cov_b, nb):
    """Brute-force check that two covering digraphs are isomorphic."""
    if na != nb or len(cov_a) != len(cov_b):
        return None
    sb = set(cov_b)
    for perm in itertools.permutations(range(nb)):
        if all((perm[x], perm[y]) in sb for x, y in cov_a):
            return perm
    return None


if __name__ == '__main__':
    path, want = sys.argv[1], sys.argv[2]
    algs = read_algebras(path)
    n, ops = algs[want]
    univ = con(n, ops)
    cov = covers(univ, n)
    print(f"{want}: |A| = {n}, {len(ops)} unary ops, |Con(A)| = {len(univ)}")
    print(f"  covering relations ({len(cov)}): {sorted(cov)}")
    # L28: 0<1<2<3<5<6 and 0<4<6  (node numbering from the paper's tikz)
    L28 = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 6), (0, 4), (4, 6)]
    p = iso_to(cov, len(univ), L28, 7)
    print(f"  isomorphic to L28? {'YES' if p else 'NO'}")
