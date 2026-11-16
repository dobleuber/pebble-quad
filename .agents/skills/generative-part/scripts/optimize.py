"""Step 1: grow a part by topology optimization (SIMP, PyTopo3D) from its supports and its load cases.

    python optimize.py <problems.py> <part> [voxel_mm] [volume_fraction] [min_member_voxels]

Writes out/<part>_rho.npy beside the problems file: the density field [y, x, z] and, beside it, the voxel size.
Needs pytopo3d 0.3 (setup_env.sh installs it): this step reaches into its optimizer.
"""
import os
import time
import warnings

import numpy as np
import pytopo3d.core.optimizer as optimizer
from pytopo3d.core.compliance import element_compliance
from pytopo3d.utils.assembly import build_force_vector

from genpart import load, union

problem, rest = load(__doc__.split("\n")[2].strip())
h = float(rest[0]) if len(rest) > 0 else problem.voxel
volfrac = float(rest[1]) if len(rest) > 1 else problem.volfrac
rmin = float(rest[2]) if len(rest) > 2 else problem.rmin
warnings.filterwarnings("ignore", message="PyTopo3D 0.3.0 fixed")      # the force axes: this code was written after the fix

X, Y, Z = problem.coords(h, layout="yxz")
ny, nx, nz = X.shape
obstacle = (problem.envelope(X, Y, Z) > 0) | (union(problem.keepout, X, Y, Z) < 0)
solid = (union(problem.preserve, X, Y, Z) < 0) & ~obstacle
forces = [problem.load_field(case, X, Y, Z, ~obstacle) for case in problem.cases]
support = (union(problem.support, X, Y, Z) < 0) & ~obstacle

space, kept = (~obstacle).sum(), solid.sum()
print(f"{problem.name}: grid {nx} x {ny} x {nz} = {nx * ny * nz} cells of {h} mm; design space {space * h ** 3:.0f} mm3, of it "
      f"preserved {kept * h ** 3:.0f} mm3 ({kept / space:.2f}); volume fraction {volfrac}; cases {', '.join(problem.cases)}", flush=True)
if not support.sum():
    raise SystemExit(f"{problem.name}: no cell of the design space is held: check `support` against the keep-outs and the envelope")
if volfrac < kept / space + 0.03:
    raise SystemExit(f"{problem.name}: the preserved features alone fill {kept / space:.2f} of the design space and the volume "
                     f"fraction is {volfrac}: nothing is left to grow. Raise volfrac above {kept / space + 0.05:.2f} or preserve less.")
if nx * ny * nz > 60000:
    print(f"{problem.name}: {nx * ny * nz} cells is a large problem here (minutes per iteration, GBs of memory): a coarser voxel "
          f"is the first thing to try", flush=True)


names = list(problem.cases)
balance = problem.balance if problem.balance != "auto" else ("worst" if problem.baseline else "sum")
of_baseline = None                                           # the baseline's compliance in each case, in the optimizer's units
if problem.baseline:
    import trimesh

    from fe import VoxelModel, voxelize
    model = VoxelModel(problem, h)
    solved = model.solve(voxelize(model, trimesh.load(os.path.join(problem.folder, problem.baseline))))
    of_baseline = [solved[name]["compliance"] * problem.youngs * h for name in names]
if balance == "worst" and of_baseline is None:
    raise SystemExit(f'{problem.name}: balance="worst" measures each case against the baseline, and the problem names none')
POWER = 6                                                    # how hard "worst" leans on the worst case (a 6-norm)


class AllCases(optimizer.ComplianceEvaluator):
    """PyTopo3D grows a part for one load. This grows it for all the cases at once: one assembly and one
    factorization per iteration, a solve per case. Each case's compliance is taken as a share of a reference, so
    a case the part resists easily weighs as much as one it does not. "sum" adds the shares, each of what the
    case's compliance was for the first, even fill. "worst" takes their 6-norm, each a share of the baseline's
    compliance in that case: it follows whichever case is furthest behind the part being replaced."""

    def __init__(self, **given):
        super().__init__(**given)
        self.F = np.stack([build_force_vector(nx, ny, nz, self.ndof, f) for f in forces], axis=1)
        self.reference = of_baseline if balance == "worst" else None
        self.each = None

    def evaluate(self, xPhys, penal):
        E0, Emin = self.E0, self.Emin
        self.K.data[:] = 0.0
        np.add.at(self.K.data, self.dup2uniq, np.kron(Emin + xPhys.ravel(order="F") ** penal * (E0 - Emin), self.KE.ravel()))
        free = self.freedofs0
        U = np.zeros(self.F.shape)
        U[free] = np.asarray(self.solver_func(self.K[free, :][:, free], self.F[free])).reshape(len(free), -1)
        ce = [element_compliance(U[:, k], self.edofMat, self.KE).reshape(self.shape, order="F") for k in range(U.shape[1])]
        each = [float(((Emin + xPhys ** penal * (E0 - Emin)) * e).sum()) for e in ce]
        if self.reference is None:
            self.reference = list(each)
        shares = np.array([problem.weights.get(name, 1.0) * c / r for name, c, r in zip(names, each, self.reference)])
        self.each = each
        if balance == "worst":
            objective = float((shares ** POWER).sum() ** (1 / POWER))
            lean = (shares / objective) ** (POWER - 1)       # d objective / d share
        else:
            objective, lean = float(shares.sum()), np.ones(len(shares))
        ce = sum(w * problem.weights.get(name, 1.0) / r * e for w, name, r, e in zip(lean, names, self.reference, ce))
        dc = -penal * (E0 - Emin) * xPhys ** (penal - 1) * ce
        dc = (self.H * (dc.ravel(order="F") / self.Hs)).reshape(self.shape, order="F")
        dv = (self.H * (np.ones(xPhys.size) / self.Hs)).reshape(self.shape, order="F")
        dc[self.obstacle_mask] = dv[self.obstacle_mask] = 0.0
        return objective, dc, dv


kept_evaluators = []
make = AllCases.__init__


def remember(self, **given):
    make(self, **given)
    kept_evaluators.append(self)


AllCases.__init__ = remember

# PyTopo3D has voids it must keep (the obstacle mask) but no solids: hold the preserved features at full
# density after every update, so the structure grows onto them instead of rebuilding them.
update = optimizer.optimality_criteria_update


def update_keeping_solids(x, *args, **kwargs):
    xnew, change = update(x, *args, **kwargs)
    xnew[solid] = 1.0
    return xnew, change


optimizer.ComplianceEvaluator = AllCases
optimizer.optimality_criteria_update = update_keeping_solids

t0 = time.time()
rho = optimizer.top3d(nx, ny, nz, volfrac, 3.0, rmin, 0.5, obstacle_mask=obstacle, force_field=forces[0],
                      support_mask=support, tolx=0.02, maxloop=problem.iterations)
rho = rho[0] if isinstance(rho, tuple) else rho
np.save(problem.path("out", f"{problem.name}_rho.npy"), rho)
with open(problem.path("out", f"{problem.name}_rho.txt"), "w") as f:
    f.write(f"{h}\n")
print(f"{problem.name}: solved in {time.time() - t0:.0f} s; solid {(rho > 0.5).sum() * h ** 3:.0f} mm3 before cleanup", flush=True)
if of_baseline and kept_evaluators:                          # an early sign, on the density field (grey cells count as weak
    print(f"{problem.name}: compliance over the baseline's as optimized, {balance} (under 1 is stiffer): "     # material: the finished part does better)
          + ", ".join(f"{name} {c / r:.2f}" for name, c, r in zip(names, kept_evaluators[-1].each, of_baseline)), flush=True)
