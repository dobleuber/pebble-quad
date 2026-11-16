"""Step 1: grow a part by topology optimization (SIMP, PyTopo3D) from its supports and its load cases.

    python generative/optimize.py <part> [voxel_mm] [volume_fraction] [min_member_voxels]

Writes generative/out/<part>_rho.npy: the density field [y, x, z] and, beside it, the voxel size.
Needs pytopo3d (uv run --with pytopo3d ...).
"""
import os
import sys
import time

import numpy as np
import pytopo3d.core.optimizer as optimizer
from pytopo3d.core.compliance import element_compliance
from pytopo3d.utils.assembly import build_force_vector

from problems import PROBLEMS, union

problem = PROBLEMS[sys.argv[1]]()
h = float(sys.argv[2]) if len(sys.argv) > 2 else problem.voxel
volfrac = float(sys.argv[3]) if len(sys.argv) > 3 else problem.volfrac
rmin = float(sys.argv[4]) if len(sys.argv) > 4 else problem.rmin
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

X, Y, Z = problem.coords(h, layout="yxz")
ny, nx, nz = X.shape
obstacle = (problem.envelope(X, Y, Z) > 0) | (union(problem.keepout, X, Y, Z) < 0)
solid = (union(problem.preserve, X, Y, Z) < 0) & ~obstacle
forces = [problem.load_field(case, X, Y, Z, ~obstacle) for case in problem.cases]
support = (union(problem.support, X, Y, Z) < 0) & ~obstacle


class AllCases(optimizer.ComplianceEvaluator):
    """PyTopo3D grows a part for one load. This grows it for all the cases at once: one assembly and one
    factorization per iteration, a solve per case, and as objective the sum of the cases' compliances, each as
    a share of what it was for the first, even fill - so a case the part resists easily weighs as much as one
    it does not."""

    def __init__(self, **given):
        super().__init__(**given)
        self.F = np.stack([build_force_vector(nx, ny, nz, self.ndof, f) for f in forces], axis=1)
        self.weights = None

    def evaluate(self, xPhys, penal):
        E0, Emin = self.E0, self.Emin
        self.K.data[:] = 0.0
        np.add.at(self.K.data, self.dup2uniq, np.kron(Emin + xPhys.ravel(order="F") ** penal * (E0 - Emin), self.KE.ravel()))
        free = self.freedofs0
        U = np.zeros(self.F.shape)
        U[free] = np.asarray(self.solver_func(self.K[free, :][:, free], self.F[free])).reshape(len(free), -1)
        ce = [element_compliance(U[:, k], self.edofMat, self.KE).reshape(self.shape, order="F") for k in range(U.shape[1])]
        each = [float(((Emin + xPhys ** penal * (E0 - Emin)) * e).sum()) for e in ce]
        if self.weights is None:
            self.weights = [1 / c for c in each]
        self.each = each
        ce = sum(w * e for w, e in zip(self.weights, ce))
        dc = -penal * (E0 - Emin) * xPhys ** (penal - 1) * ce
        dc = (self.H * (dc.ravel(order="F") / self.Hs)).reshape(self.shape, order="F")
        dv = (self.H * (np.ones(xPhys.size) / self.Hs)).reshape(self.shape, order="F")
        dc[self.obstacle_mask] = dv[self.obstacle_mask] = 0.0
        return sum(w * c for w, c in zip(self.weights, each)), dc, dv


optimizer.ComplianceEvaluator = AllCases

# PyTopo3D has voids it must keep (the obstacle mask) but no solids: hold the preserved features at full
# density after every update, so the structure grows onto them instead of rebuilding them.
update = optimizer.optimality_criteria_update


def update_keeping_solids(x, *args, **kwargs):
    xnew, change = update(x, *args, **kwargs)
    xnew[solid] = 1.0
    return xnew, change


optimizer.optimality_criteria_update = update_keeping_solids

free = (~obstacle).sum() * h ** 3
print(f"{problem.name}: grid {nx} x {ny} x {nz}, {h} mm voxels; design space {free:.0f} mm3, of it preserved "
      f"{solid.sum() * h ** 3:.0f} mm3; cases {', '.join(problem.cases)}", flush=True)
t0 = time.time()
rho = optimizer.top3d(nx, ny, nz, volfrac, 3.0, rmin, 0.5, obstacle_mask=obstacle, force_field=forces[0],
                      support_mask=support, tolx=0.02, maxloop=80)
rho = rho[0] if isinstance(rho, tuple) else rho
np.save(os.path.join(OUT, f"{problem.name}_rho.npy"), rho)
with open(os.path.join(OUT, f"{problem.name}_rho.txt"), "w") as f:
    f.write(f"{h}\n")
print(f"{problem.name}: solved in {time.time() - t0:.0f} s; solid {(rho > 0.5).sum() * h ** 3:.0f} mm3", flush=True)
