"""The voxel finite-element model the steps share: 8-node bricks on a problem's grid, held and loaded as the
problem says, solved once per load case (one factorization). Needs pytopo3d (and its pypardiso)."""
import numpy as np
import scipy.sparse as sp
from pytopo3d.utils.assembly import build_edof, build_force_vector, build_supports
from pytopo3d.utils.solver import get_solver
from pytopo3d.utils.stiffness import lk_H8

from genpart import union


class VoxelModel:
    def __init__(self, problem, h):
        self.problem, self.h = problem, h
        self.X, self.Y, self.Z = problem.coords(h, layout="yxz")
        self.ny, self.nx, self.nz = self.X.shape
        self.ndof = 3 * (self.nx + 1) * (self.ny + 1) * (self.nz + 1)
        self.edof, self.iK, self.jK = build_edof(self.nx, self.ny, self.nz)
        self.KE = lk_H8(problem.poisson)
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
        U /= p.youngs * h                                    # unit bricks of unit modulus -> mm
        out = {}
        for k, (case, field) in enumerate(fields.items()):
            ue = U[:, k][self.edof - 1]
            energy = 0.5 * np.einsum("ei,ij,ej->e", ue, self.KE, ue) * stiff * p.youngs * h / h ** 3
            out[case] = {"compliance": float(F[:, k] @ U[:, k]), "energy": energy.reshape(shape, order="F"),
                         "touched": support | (np.abs(field).sum(axis=3) > 0)}
        return out


def voxelize(model, mesh):
    """Which of the model's cells have their centre inside a mesh: a ray up each column, counting crossings."""
    X, Y, Z, nx, ny, nz = model.X, model.Y, model.Z, model.nx, model.ny, model.nz
    zc = Z[0, 0, :]
    origins = np.stack([X[:, :, 0].ravel() + 1.37e-4, Y[:, :, 0].ravel() + 0.71e-4, np.full(nx * ny, zc[0] - 50.0)], axis=1)
    hits, ray, _ = mesh.ray.intersects_location(origins, np.tile([0.0, 0.0, 1.0], (len(origins), 1)), multiple_hits=True)
    crossings = np.zeros((nx * ny, nz + 1), int)
    np.add.at(crossings, (ray, np.searchsorted(zc, hits[:, 2])), 1)
    return (np.cumsum(crossings, axis=1)[:, :nz] % 2 == 1).reshape(ny, nx, nz)
