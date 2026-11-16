"""The voxel finite-element model the pipeline's steps share: 8-node bricks on a problem's grid, held and
loaded as the problem says, solved once per load case (one factorization). Needs pytopo3d (and its pypardiso)."""
import numpy as np
import scipy.sparse as sp
from pytopo3d.utils.assembly import build_edof, build_force_vector, build_supports
from pytopo3d.utils.solver import get_solver
from pytopo3d.utils.stiffness import lk_H8

from problems import union

E, NU = 3500.0, 0.3                                       # PLA: MPa, -


class VoxelModel:
    def __init__(self, problem, h):
        self.problem, self.h = problem, h
        self.X, self.Y, self.Z = problem.coords(h, layout="yxz")
        self.ny, self.nx, self.nz = self.X.shape
        self.ndof = 3 * (self.nx + 1) * (self.ny + 1) * (self.nz + 1)
        self.edof, self.iK, self.jK = build_edof(self.nx, self.ny, self.nz)
        self.KE = lk_H8(NU)
        self.solver, _ = get_solver(False)

    def solve(self, solid):
        """For a boolean field [y, x, z]: per case, the compliance (N*mm), the strain energy density per cell
        (N*mm/mm3) and the cells the case touches (held or loaded)."""
        p, h, shape = self.problem, self.h, self.X.shape
        support = (union(p.support, self.X, self.Y, self.Z) < 0) & solid
        assert support.sum(), f"{p.name}: no material where the part is held"
        free, _ = build_supports(self.nx, self.ny, self.nz, self.ndof, support)
        stiff = np.where(solid.ravel(order="F"), 1.0, 1e-9)
        K = sp.coo_matrix((np.kron(stiff, self.KE.ravel()), (self.iK - 1, self.jK - 1)), shape=(self.ndof, self.ndof)).tocsr()
        fields = {case: p.load_field(case, self.X, self.Y, self.Z, solid) for case in p.cases}
        F = np.stack([build_force_vector(self.nx, self.ny, self.nz, self.ndof, f) for f in fields.values()], axis=1)
        U = np.zeros(F.shape)
        U[free] = np.asarray(self.solver(K[free, :][:, free], F[free])).reshape(len(free), -1)
        U /= E * h                                           # unit bricks of unit modulus -> mm
        out = {}
        for k, (case, field) in enumerate(fields.items()):
            ue = U[:, k][self.edof - 1]
            energy = 0.5 * np.einsum("ei,ij,ej->e", ue, self.KE, ue) * stiff * E * h / h ** 3
            out[case] = {"compliance": float(F[:, k] @ U[:, k]), "energy": energy.reshape(shape, order="F"),
                         "touched": support | (np.abs(field).sum(axis=3) > 0)}
        return out
